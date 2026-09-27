// Same SDK owner. CurrentUser bootstrap only configures/restores; never provisions
// authority or activates an operation. Companion source belongs under AddOns.
using System;
using System.Collections.Generic;
using System.Collections.Concurrent;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Text;
using System.Web.Script.Serialization;
using Arms.NativeSim;
using NinjaTrader.Cbi;

namespace NinjaTrader.NinjaScript.Indicators
{
    public partial class ArmsSimNativeSubmitBridgeV2
    {
        private readonly object controlledSync = new object();
        private readonly Dictionary<string,Order> controlledOrders = new Dictionary<string,Order>(StringComparer.Ordinal);
        private readonly HashSet<string> polledObservations = new HashSet<string>(StringComparer.Ordinal);
        private byte[] controlledKey;
        private Dictionary<string,string> controlledClaims;
        private long controlledGeneration;
        private string controlledRiskVersion, controlledStateDirectory, controlledReceiptDirectory;
        private Func<long> controlledClock;
        private ControlledOperationV3 controlledOperation;
        private ControlledAdmissionV3 controlledAdmission;
        private int controlledExitObserved;
        private System.Windows.Threading.DispatcherTimer controlledServiceTimer;
        private bool controlledServiceStopped;
        private bool controlledBootstrapAttempted,controlledBootstrapReady,controlledObservationOnly;
        private Dictionary<string,object> controlledCommissioning=new Dictionary<string,object>();
        private void BootstrapControlledV3(string authorityRoot,Dictionary<string,string> expected,Func<long> clock)
        {
            lock(controlledSync)
            {
                if(controlledBootstrapAttempted) return;
                controlledBootstrapAttempted=true;
                controlledObservationOnly=true;
                controlledCommissioning=new Dictionary<string,object> {
                    {"schema","ARMS_CONTROLLED_COMMISSIONING_V3"},{"controlled_v3_configured",false},
                    {"authority_loaded",false},{"config_signature_valid",false},{"restore_status","NOT_STARTED"},
                    {"command_path_ready",false},{"activation_path_ready",false},{"state_path_ready",false},
                    {"reconciliation_path_ready",false},{"last_configuration_error",""}};
                foreach(string name in new[]{"configuration_generation","authority_id","backend_account_id","native_account","provider","instrument","runtime_generation"})
                    controlledCommissioning[name]="";
                try
                {
                    ValidateSelectedAccount();
                    if(authorityRoot==null) authorityRoot=ControlledConfigurationV3.AuthorityRoot();
                    using(var config=ControlledConfigurationV3.Load(authorityRoot,expected,clock()))
                    {
                        var v=config.Values;
                        if(selectedAccount.Name!=v["native_account"] || selectedAccount.Provider.ToString()!=v["provider"] ||
                            InstrumentName!=v["instrument"] || CommandDirectory!=v["command_directory"] || ActivationDirectory!=v["activation_directory"])
                            throw new InvalidDataException("OWNER_CONFIGURATION_MISMATCH");
                        ConfigureControlledV3(config.Key,ControlledAdmissionV3.AccountFields.ToDictionary(n=>n,n=>v[n]),
                            long.Parse(v["runtime_generation"],CultureInfo.InvariantCulture),v["risk_version"],v["state_directory"],v["reconciliation_directory"],clock);
                        foreach(string name in new[]{"configuration_generation","authority_id","backend_account_id","native_account","provider","instrument","runtime_generation"})
                            controlledCommissioning[name]=v[name];
                        controlledCommissioning["authority_loaded"]=true;
                        controlledCommissioning["config_signature_valid"]=true;
                        foreach(string name in new[]{"command_path_ready","activation_path_ready","state_path_ready","reconciliation_path_ready"}) controlledCommissioning[name]=true;
                        if(Directory.GetFiles(controlledStateDirectory,"*.state").Length!=0)
                        {
                            RestoreControlledV3();
                            controlledCommissioning["restore_status"]=controlledOperation.ReconciliationRequired?"RECONCILIATION_REQUIRED":controlledOperation.Status;
                        }
                        else controlledCommissioning["restore_status"]="NO_PERSISTED_OPERATION";
                        RestoreManualReconciliation();
                        if(emergencyFlattenAwaitingConfirmation) controlledCommissioning["restore_status"]="MANUAL_RECONCILIATION_REQUIRED";
                        controlledBootstrapReady=true;
                        controlledCommissioning["controlled_v3_configured"]=true;
                    }
                }
                catch(Exception error)
                {
                    controlledBootstrapReady=false;
                    controlledCommissioning["authority_loaded"]=false;
                    if(controlledOperation!=null) {controlledOperation.Dispose();controlledOperation=null;}
                    if(controlledKey!=null) {Array.Clear(controlledKey,0,controlledKey.Length);controlledKey=null;}
                    controlledCommissioning["restore_status"]="DISABLED";
                    // Never log config contents, key material, or arbitrary exception text.
                    controlledCommissioning["last_configuration_error"]=error is InvalidDataException &&
                        System.Text.RegularExpressions.Regex.IsMatch(error.Message,@"\A[A-Z][A-Za-z_]{1,100}\z")?error.Message:error.GetType().Name;
                }
                WriteControlledCommissioningStatus();
            }
        }
        private void WriteControlledCommissioningStatus()
        {
            if(!controlledBootstrapAttempted || string.IsNullOrWhiteSpace(RuntimeSnapshotDirectory)) return;
            string temporary=null;
            try
            {
                lock(controlledSync)
                {
                    string root=ControlledConfigurationV3.SafePath(RuntimeSnapshotDirectory,false);
                    if(!Directory.Exists(root)) return;
                    controlledCommissioning["observed_at"]=DateTime.UtcNow.ToString("o",CultureInfo.InvariantCulture);
                    controlledCommissioning["native_submit_enabled"]=NATIVE_SUBMIT_ENABLED;
                    controlledCommissioning["auto_retry_allowed"]=AUTO_RETRY_ALLOWED;
                    controlledCommissioning["reconciliation_fence"]=!controlledBootstrapReady?(object)"UNKNOWN":
                        emergencyFlattenAwaitingConfirmation || (controlledOperation!=null && controlledOperation.ReconciliationRequired);
                    string path=Path.Combine(root,"controlled-v3-commissioning-status.json");
                    temporary=path+"."+Guid.NewGuid().ToString("N")+".tmp";
                    byte[] bytes=new UTF8Encoding(false).GetBytes(new JavaScriptSerializer().Serialize(controlledCommissioning));
                    using(var file=new FileStream(temporary,FileMode.CreateNew,FileAccess.Write,FileShare.None)) {file.Write(bytes,0,bytes.Length);file.Flush(true);}
                    if(File.Exists(path)) File.Replace(temporary,path,null);else File.Move(temporary,path);
                }
            }
            catch {Print("ARMS_CONTROLLED_COMMISSIONING_WRITE_FAILED");}
            finally {if(temporary!=null && File.Exists(temporary)) File.Delete(temporary);}
        }
        private void StartControlledService()
        {
            if(ChartControl==null) throw new InvalidOperationException("An explicit bridge dispatcher is required.");
            ChartControl.Dispatcher.InvokeAsync(new Action(()=> {
                if(controlledServiceStopped || controlledServiceTimer!=null) return;
                // Scheduling only: use the approved acknowledgement window, not
                // a new risk threshold. Manual service retains the existing cadence.
                long ticks=controlledAdmission==null?TimeSpan.FromSeconds(5).Ticks:Math.Max(1,controlledAdmission.Number("protection_timeout_us")/4*10);
                controlledServiceTimer=new System.Windows.Threading.DispatcherTimer {Interval=TimeSpan.FromTicks(ticks)};
                controlledServiceTimer.Tick+=OnControlledService;
                controlledServiceTimer.Start();
            }));
        }
        private void OnControlledService(object sender, EventArgs args)
        {
            if(controlledServiceStopped || controlledObservationOnly) return;
            try { ReconcileControlledV3(); AdvanceManualEmergencyRecovery(); }
            catch(Exception error) { Print("ARMS_CONTROLLED_RECONCILIATION_REQUIRED "+error.GetType().Name); }
        }
        private void ScheduleControlledReconciliation()
        {
            if(!controlledServiceStopped && ChartControl!=null)
                ChartControl.Dispatcher.InvokeAsync(new Action(()=>OnControlledService(null,EventArgs.Empty)));
        }
        private sealed class CapturedCallback
        {
            internal Order Order; internal Account Account; internal string OrderId,Name,ExecutionId,State;
            internal int Quantity; internal double Price; internal bool IsExecution;
        }
        private readonly ConcurrentQueue<CapturedCallback> controlledCallbacks = new ConcurrentQueue<CapturedCallback>();
        // SDK callbacks never wait on the operation lock held across Submit.
        // Persist raw facts first; apply captured scalar values on the owner loop.
        private void QueueControlledOrder(Order order)
        {
            if(controlledOperation==null || order==null) return;
            var item=new CapturedCallback {Order=order,Account=order.Account,OrderId=order.OrderId,Name=order.Name,
                State=order.OrderState.ToString(),Quantity=order.Filled,Price=order.AverageFillPrice};
            RecordControlledRaw("ORDER",order,"",item.Quantity,item.Price);
            controlledCallbacks.Enqueue(item);
            ScheduleControlledReconciliation();
        }
        private void QueueControlledExecution(Execution execution)
        {
            if(controlledOperation==null || execution==null) return;
            var order=execution.Order;
            if(order==null || controlledOperation.RoleForName(order.Name)!="ENTRY")
                System.Threading.Interlocked.Exchange(ref controlledExitObserved,1);
            var item=new CapturedCallback {Order=order,Account=execution.Account,OrderId=order==null?"":order.OrderId,
                Name=order==null?"":order.Name,ExecutionId=execution.ExecutionId,Quantity=execution.Quantity,Price=execution.Price,IsExecution=true};
            RecordControlledRaw("EXECUTION",order,item.ExecutionId,item.Quantity,item.Price);
            controlledCallbacks.Enqueue(item);
            ScheduleControlledReconciliation();
        }
        private void DrainControlledCallbacks()
        {
            CapturedCallback item;
            while(controlledCallbacks.TryDequeue(out item))
            {
                if(!ReferenceEquals(item.Account,selectedAccount) || !ControlledOwnedOrder(item.Order) ||
                    item.Name!=item.Order.Name || item.OrderId!=item.Order.OrderId)
                { controlledOperation.UnassignedEvidence(); continue; }
                string role=controlledOperation.RoleForName(item.Name);
                if(item.IsExecution) controlledOperation.Execution(role,item.ExecutionId,item.Quantity,(decimal)item.Price,item.OrderId);
                else controlledOperation.OrderUpdate(role,item.State,item.OrderId,item.Quantity);
            }
        }

        // Privileged dependency injection. Key/claims never come from command,
        // activation, runtime snapshot JSON, or a user-supplied signing key field.
        public void ConfigureControlledV3(byte[] trustedKey, Dictionary<string,string> trustedClaims,
            long generation, string riskVersion, string stateDirectory, string receiptDirectory, Func<long> clock)
        {
            lock(controlledSync)
            {
                if(controlledKey!=null || trustedKey==null || trustedKey.Length<32 || trustedClaims==null ||
                    !new HashSet<string>(ControlledAdmissionV3.AccountFields).SetEquals(trustedClaims.Keys) ||
                    trustedClaims["execution_domain"]!="SIM_NATIVE" || generation<1 || string.IsNullOrWhiteSpace(riskVersion) ||
                    !Path.IsPathRooted(stateDirectory) || !Directory.Exists(stateDirectory) ||
                    !Path.IsPathRooted(receiptDirectory) || !Directory.Exists(receiptDirectory) || clock==null)
                    throw new InvalidDataException("Explicit immutable controlled authority required.");
                controlledKey=(byte[])trustedKey.Clone(); controlledClaims=new Dictionary<string,string>(trustedClaims);
                controlledGeneration=generation; controlledRiskVersion=riskVersion;
                controlledStateDirectory=stateDirectory; controlledReceiptDirectory=receiptDirectory; controlledClock=clock;
            }
        }
        private static Dictionary<string,object> ControlledJson(string path)
        {
            var info=new FileInfo(path);
            if(!info.Exists || info.Length>131072) throw new InvalidDataException("Missing/oversized controlled artifact.");
            var value=new JavaScriptSerializer().Deserialize<Dictionary<string,object>>(File.ReadAllText(path,Encoding.UTF8));
            if(value==null) throw new InvalidDataException("Invalid controlled artifact.");
            return value;
        }
        private static string ControlledText(Dictionary<string,object> values,string key)
        {
            object value; if(!values.TryGetValue(key,out value) || !(value is string)) throw new InvalidDataException("Missing controlled identity.");
            return (string)value;
        }
        private void AttemptControlledV3()
        {
            lock(controlledSync)
            {
                ValidateSelectedAccount();
                if(controlledKey==null || controlledOperation!=null || submitAttempted || !RequestOneShotSubmit ||
                    RequestEmergencyFlatten || OperatorArmToken!=REQUIRED_ARM_TOKEN || Quantity!=1)
                    throw new InvalidOperationException("Controlled entry authority unavailable or already attempted.");
                if(!System.Text.RegularExpressions.Regex.IsMatch(CommandId ?? "",@"\A[A-Za-z0-9_.-]{1,100}\z"))
                    throw new InvalidDataException("Unsafe command identity.");
                var command=ControlledJson(Path.Combine(CommandDirectory,CommandId+".json"));
                if(!new HashSet<string>(new[]{"command","command_id","operation_id","client_order_id","payload"}).SetEquals(command.Keys) ||
                    ControlledText(command,"command")!="SUBMIT_ORDER" || !(command["payload"] is Dictionary<string,object>))
                    throw new InvalidDataException("Invalid command schema.");
                var payload=(Dictionary<string,object>)command["payload"];
                if(!new HashSet<string>(new[]{"schema","admission_wire"}).SetEquals(payload.Keys) || ControlledText(payload,"schema")!="ARMS_SIM_COMMAND_V3")
                    throw new InvalidDataException("Authenticated command required.");
                byte[] wire=Convert.FromBase64String(ControlledText(payload,"admission_wire"));
                controlledAdmission=ControlledAdmissionV3.Read(wire,controlledKey);
                foreach(string name in new[]{"command_id","operation_id","client_order_id"})
                    if(ControlledText(command,name)!=controlledAdmission[name]) throw new InvalidDataException("Command admission mismatch.");
                if(CommandId!=controlledAdmission["command_id"] || InstrumentName!=controlledAdmission["instrument"] || Side!=controlledAdmission["side"])
                    throw new InvalidDataException("Configured command/instrument/side mismatch.");
                string activationPath=Path.Combine(ActivationDirectory,CommandId+".arm.json");
                var activation=ControlledJson(activationPath);
                if(!new HashSet<string>(new[]{"schema","command_id","activation_id","admission_digest","admission_wire"}).SetEquals(activation.Keys) ||
                    ControlledText(activation,"schema")!="ARMS_SIM_ACTIVATION_V3" || ControlledText(activation,"command_id")!=CommandId ||
                    ControlledText(activation,"activation_id")!=controlledAdmission["activation_id"] ||
                    ControlledText(activation,"admission_digest")!=controlledAdmission.Digest ||
                    ControlledText(activation,"admission_wire")!=ControlledText(payload,"admission_wire"))
                    throw new InvalidDataException("Activation admission mismatch.");
                controlledAdmission.Validate(controlledClock(),ControlledSnapshot(),InstrumentName);
                controlledOperation=new ControlledOperationV3(controlledAdmission,new ControlledAccountAdapter(this),controlledClock,
                    controlledKey,controlledStateDirectory,InstrumentName);
                if(!File.Exists(activationPath+".consumed"))
                {
                    string[] baseline;
                    lock(selectedAccount.Executions) baseline=selectedAccount.Executions.Where(e=>e.Order!=null && e.Order.Instrument!=null && e.Order.Instrument.FullName==InstrumentName).Select(e=>e.ExecutionId).ToArray();
                    controlledOperation.RecordExecutionBaseline(baseline);
                }
                submitAttempted=true;
                if(!controlledObservationOnly) StartControlledService();
                controlledOperation.Enter(CommandId,controlledAdmission.Digest,controlledAdmission["activation_id"],controlledAdmission.Digest,
                    true,File.Exists(activationPath+".consumed"),NATIVE_SUBMIT_ENABLED,()=> {
                        using(var file=new FileStream(activationPath+".consumed",FileMode.CreateNew,FileAccess.Write,FileShare.None))
                        { byte[] bytes=Encoding.ASCII.GetBytes(controlledAdmission.Digest); file.Write(bytes,0,bytes.Length); file.Flush(true); }
                    });
            }
        }
        // Recovery-only restart attachment. Never reads/consumes a new activation
        // or calls Enter. Missing native order IDs remain unassigned evidence.
        public void RestoreControlledV3()
        {
            lock(controlledSync)
            {
                ValidateSelectedAccount();
                if(controlledKey==null || controlledOperation!=null || !Directory.GetFiles(controlledStateDirectory,"*.state").Any())
                    throw new InvalidDataException("Existing durable controlled operation required.");
                if(!System.Text.RegularExpressions.Regex.IsMatch(CommandId ?? "",@"\A[A-Za-z0-9_.-]{1,100}\z"))
                    throw new InvalidDataException("Unsafe recovery command identity.");
                var command=ControlledJson(Path.Combine(CommandDirectory,CommandId+".json"));
                var payload=command["payload"] as Dictionary<string,object>;
                if(payload==null || ControlledText(payload,"schema")!="ARMS_SIM_COMMAND_V3" || ControlledText(command,"command")!="SUBMIT_ORDER")
                    throw new InvalidDataException("Authenticated recovery command required.");
                controlledAdmission=ControlledAdmissionV3.Read(Convert.FromBase64String(ControlledText(payload,"admission_wire")),controlledKey);
                foreach(string name in new[]{"command_id","operation_id","client_order_id"})
                    if(ControlledText(command,name)!=controlledAdmission[name]) throw new InvalidDataException("Recovery command mismatch.");
                foreach(string name in ControlledAdmissionV3.AccountFields)
                    if(controlledClaims[name]!=controlledAdmission[name]) throw new InvalidDataException("Recovery account claims mismatch.");
                if(controlledAdmission["account"]!="Sim101" || controlledAdmission["provider"]!="Simulator" ||
                    controlledAdmission["command_id"]!=CommandId || controlledAdmission["instrument"]!=InstrumentName ||
                    controlledAdmission.Number("runtime_generation")!=controlledGeneration || controlledAdmission["risk_version"]!=controlledRiskVersion)
                    throw new InvalidDataException("Recovery identity/generation mismatch.");
                submitAttempted=true;
                controlledOperation=new ControlledOperationV3(controlledAdmission,new ControlledAccountAdapter(this),controlledClock,
                    controlledKey,controlledStateDirectory,InstrumentName);
                if(!controlledObservationOnly) StartControlledService();
            }
        }
        private void ControlledMutationGuard()
        {
            ValidateSelectedAccount();
            if(!NATIVE_SUBMIT_ENABLED || controlledObservationOnly || (controlledBootstrapAttempted && !controlledBootstrapReady) || controlledOperation==null || controlledAdmission==null || controlledKey==null ||
                selectedAccount.Name!="Sim101" || selectedAccount.Provider!=Provider.Simulator ||
                InstrumentName!=controlledAdmission["instrument"] || controlledGeneration!=controlledAdmission.Number("runtime_generation") ||
                selectedAccount.ConnectionStatus!=ConnectionStatus.Connected)
                throw new InvalidOperationException("Native controlled capability disabled or identity changed.");
            controlledOperation.RequireMutationAuthority();
            RequireNoManualReconciliation();
        }
        private ControlledSnapshotV3 ControlledSnapshot()
        {
            ValidateSelectedAccount();
            var positions=new List<Position>(); var orders=new List<Order>();
            lock(selectedAccount.Positions) positions.AddRange(selectedAccount.Positions.Where(p=>p.Instrument!=null && p.Instrument.FullName==InstrumentName && p.MarketPosition!=MarketPosition.Flat));
            lock(selectedAccount.Orders) orders.AddRange(selectedAccount.Orders.Where(o=>o.Instrument!=null && o.Instrument.FullName==InstrumentName && !ControlledTerminal(o.OrderState)));
            if(positions.Count>1) throw new InvalidDataException("Ambiguous controlled exposure.");
            return new ControlledSnapshotV3 { Account=selectedAccount.Name,Provider=selectedAccount.Provider.ToString(),Instrument=InstrumentName,
                AccountClaims=new Dictionary<string,string>(controlledClaims),Generation=controlledGeneration,RiskVersion=controlledRiskVersion,
                Connected=selectedAccount.ConnectionStatus==ConnectionStatus.Connected,ObservedUs=controlledClock(),
                PositionQuantity=positions.Count==0?0:positions[0].Quantity,
                PositionSide=positions.Count==0?"":positions[0].MarketPosition==MarketPosition.Long?"BUY":"SELL",
                ActiveOrderNames=orders.Select(o=>o.Name ?? "").ToArray() };
        }
        private static bool ControlledTerminal(OrderState state)
        { return state==OrderState.Cancelled || state==OrderState.Filled || state==OrderState.Rejected; }
        private object CreateControlledOrder(ControlledOrderV3 spec)
        {
            ControlledMutationGuard();
            if(spec.Quantity!=1 || spec.Instrument!=InstrumentName || spec.Name!=controlledOperation.OrderName(spec.Role) || controlledOrders.ContainsKey(spec.Name))
                throw new InvalidDataException("Controlled role identity/quantity mismatch.");
            if(spec.Role=="RECOVERY_CLOSE") ValidateRecoverySubmission(null);
            if(spec.Role=="PROTECTIVE_STOP" || spec.Role=="PROFIT_TARGET") ValidateProtectionMutation();
            var instrument=NinjaTrader.Cbi.Instrument.GetInstrument(InstrumentName,true);
            var action=spec.Action=="BUY"?OrderAction.Buy:spec.Action=="SELL"?OrderAction.Sell:spec.Action=="BUY_TO_COVER"?OrderAction.BuyToCover:OrderAction.SellShort;
            if(spec.Role=="ENTRY" && spec.Action=="SELL") action=OrderAction.SellShort;
            OrderType type=spec.Type=="MARKET"?OrderType.Market:spec.Type=="STOP_MARKET"?OrderType.StopMarket:OrderType.Limit;
            Order order=selectedAccount.CreateOrder(instrument,action,type,OrderEntry.Automated,TimeInForce.Day,1,
                type==OrderType.Limit?(double)spec.Price:0.0,type==OrderType.StopMarket?(double)spec.Price:0.0,spec.Oco,spec.Name,NinjaTrader.Core.Globals.MaxDate,null);
            if(order==null) throw new InvalidOperationException("Controlled native creation returned no order.");
            controlledOrders.Add(spec.Name,order);
            if(!string.IsNullOrEmpty(order.OrderId)) controlledOperation.BindCreatedOrder(spec.Role,order.OrderId);
            return order;
        }
        private void SubmitControlledOrder(object value)
        {
            ControlledMutationGuard(); var order=value as Order; Order expected;
            if(order==null || !controlledOrders.TryGetValue(order.Name,out expected) || !ReferenceEquals(order,expected))
                throw new InvalidDataException("Unknown controlled order handle.");
            if(controlledOperation.RoleForName(order.Name)!="ENTRY" && controlledOperation.RoleForName(order.Name)!="RECOVERY_CLOSE")
                throw new InvalidDataException("Protectors require the collection submission boundary.");
            if(controlledOperation.RoleForName(order.Name)=="RECOVERY_CLOSE") ValidateRecoverySubmission(order.Name);
            selectedAccount.Submit(new[]{order});
        }
        private void ValidateProtectionMutation()
        {
            var snapshot=ControlledSnapshot();
            bool observedExit=System.Threading.Interlocked.CompareExchange(ref controlledExitObserved,0,0)!=0;
            lock(selectedAccount.Executions)
                observedExit |= selectedAccount.Executions.Any(e=>e.Order!=null && e.Order.Instrument!=null &&
                    e.Order.Instrument.FullName==InstrumentName && !controlledOperation.IsBaselineExecution(e.ExecutionId) &&
                    controlledOperation.RoleForName(e.Order.Name)!="ENTRY");
            if(observedExit || snapshot.PositionQuantity!=1 || snapshot.PositionSide!=controlledAdmission["side"])
            { controlledOperation.RequirePositionReconciliation();throw new InvalidDataException("Protection requires proven open controlled exposure with no observed exit."); }
        }
        private void SubmitControlledProtection(object stopValue,object targetValue)
        {
            ControlledMutationGuard();ValidateProtectionMutation();
            var stop=stopValue as Order;var target=targetValue as Order;
            if(stop==null || target==null || ReferenceEquals(stop,target) ||
                controlledOperation.RoleForName(stop.Name)!="PROTECTIVE_STOP" || controlledOperation.RoleForName(target.Name)!="PROFIT_TARGET" ||
                !ControlledOwnedOrder(stop) || !ControlledOwnedOrder(target) || stop.Oco!=target.Oco || string.IsNullOrEmpty(stop.Oco))
                throw new InvalidDataException("Complete approved protective pair required.");
            // One collection call; this does not assert broker-side atomicity.
            IEnumerable<Order> pair=new[]{stop,target};
            selectedAccount.Submit(pair);
        }
        private void ValidateRecoverySubmission(string pendingName)
        {
            controlledOperation.RequireRecoveryAuthority();
            if(controlledReconciledExecutions==null || controlledReconciledExecutions!=ControlledExecutionSetDigest() ||
                controlledReconciledRaw!=ControlledRawDigest() || System.Threading.Interlocked.CompareExchange(ref controlledExitObserved,0,0)!=0)
            {controlledOperation.RequirePositionReconciliation();throw new InvalidDataException("Execution evidence changed after operator reconciliation.");}
            var snapshot=ControlledSnapshot();
            if(snapshot.PositionQuantity!=1 || snapshot.PositionSide!=controlledAdmission["side"] ||
                snapshot.ActiveOrderNames.Any(name=>name!=pendingName))
                throw new InvalidDataException("Recovery exposure changed or competing order appeared; no submission.");
        }
        private void CancelControlledOrders(string[] names)
        {
            ControlledMutationGuard(); var orders=new List<Order>();
            lock(selectedAccount.Orders)
                foreach(string name in names)
                {
                    string role=controlledOperation.RoleForName(name);
                    if(role!="PROTECTIVE_STOP" && role!="PROFIT_TARGET") throw new InvalidDataException("Only owned protectors may be cancelled.");
                    var matches=selectedAccount.Orders.Where(o=>o.Name==name && ControlledOwnedOrder(o)).ToArray();
                    if(matches.Length!=1) throw new InvalidDataException("Ambiguous cancellation identity.");
                    if(!ControlledTerminal(matches[0].OrderState)) orders.Add(matches[0]);
                }
            if(orders.Count>0) selectedAccount.Cancel(orders);
        }
        private bool ControlledOwnedOrder(Order order)
        {
            if(order==null || !ReferenceEquals(order.Account,selectedAccount) || order.Instrument==null ||
                order.Instrument.FullName!=InstrumentName || order.Quantity!=1 || controlledOperation==null ||
                controlledOperation.RoleForName(order.Name)==null) return false;
            string role=controlledOperation.RoleForName(order.Name);
            OrderAction action=role=="ENTRY"?(controlledAdmission["side"]=="BUY"?OrderAction.Buy:OrderAction.SellShort):
                controlledAdmission["side"]=="BUY"?OrderAction.Sell:OrderAction.BuyToCover;
            OrderType type=role=="PROTECTIVE_STOP"?OrderType.StopMarket:role=="PROFIT_TARGET"?OrderType.Limit:OrderType.Market;
            string oco=role=="PROTECTIVE_STOP" || role=="PROFIT_TARGET"?"a3."+controlledAdmission.Digest.Substring(0,32)+".O":"";
            if(order.OrderAction!=action || order.OrderType!=type || order.Oco!=oco ||
                (type==OrderType.StopMarket && (decimal)order.StopPrice!=controlledAdmission.Price("stop_price")) ||
                (type==OrderType.Limit && (decimal)order.LimitPrice!=controlledAdmission.Price("target_price"))) return false;
            Order known;
            return (controlledOrders.TryGetValue(order.Name,out known) && ReferenceEquals(known,order)) ||
                controlledOperation.MatchesOrderIdentity(order.Name,order.OrderId);
        }
        private void RecordControlledRaw(string kind,Order order,string executionId,int quantity,double price)
        {
            // Preserve unknown evidence too; a raw record is never financial authority.
            var record=new Dictionary<string,object> { {"kind",kind},{"order_name",order==null?"":order.Name},
                {"native_order_id",order==null?"":order.OrderId},{"execution_id",executionId ?? ""},{"quantity",quantity},{"price",price},
                {"order_state",order==null?"":order.OrderState.ToString()},{"instrument",order==null || order.Instrument==null?"":order.Instrument.FullName},
                {"account",order==null || order.Account==null?"":order.Account.Name},
                {"provider",order==null || order.Account==null?"":order.Account.Provider.ToString()},
                {"action",order==null?"":order.OrderAction.ToString()},{"type",order==null?"":order.OrderType.ToString()},
                {"order_quantity",order==null?0:order.Quantity},{"order_filled",order==null?0:order.Filled},
                {"limit_price",order==null?0:order.LimitPrice},{"stop_price",order==null?0:order.StopPrice},
                {"oco",order==null?"":order.Oco},{"observed_us",controlledClock()} };
            byte[] data=Encoding.UTF8.GetBytes(new JavaScriptSerializer().Serialize(record));
            using(var file=new FileStream(Path.Combine(controlledStateDirectory,"raw-"+Guid.NewGuid().ToString("N")+".json"),FileMode.CreateNew,FileAccess.Write,FileShare.Read))
            { file.Write(data,0,data.Length); file.Flush(true); }
        }
        private void ControlledOrderCallback(Order order, bool polled = false)
        {
            lock(controlledSync)
            {
                if(controlledOperation==null) return;
                string observation=order==null?"NULL_ORDER":"O|"+order.OrderId+"|"+order.Name+"|"+order.OrderState+"|"+order.Filled+"|"+order.Quantity+"|"+order.AverageFillPrice.ToString("R",CultureInfo.InvariantCulture);
                if(!polled || polledObservations.Add(observation))
                    RecordControlledRaw("ORDER",order,"",order==null?0:order.Filled,order==null?0:order.AverageFillPrice);
                if(!ControlledOwnedOrder(order)) { controlledOperation.UnassignedEvidence(); return; }
                controlledOperation.OrderUpdate(controlledOperation.RoleForName(order.Name),order.OrderState.ToString(),order.OrderId,order.Filled);
            }
        }
        private void ControlledExecutionCallback(Execution execution, bool polled = false)
        {
            lock(controlledSync)
            {
                if(controlledOperation==null || execution==null) return;
                string observation="E|"+execution.ExecutionId+"|"+(execution.Order==null?"":execution.Order.OrderId)+"|"+execution.Quantity+"|"+execution.Price.ToString("R",CultureInfo.InvariantCulture);
                if(!polled || polledObservations.Add(observation))
                    RecordControlledRaw("EXECUTION",execution.Order,execution.ExecutionId,execution.Quantity,execution.Price);
                if(!ReferenceEquals(execution.Account,selectedAccount) || !ControlledOwnedOrder(execution.Order))
                { controlledOperation.UnassignedEvidence(); return; }
                controlledOperation.Execution(controlledOperation.RoleForName(execution.Order.Name),execution.ExecutionId,
                    execution.Quantity,(decimal)execution.Price,execution.Order.OrderId);
            }
        }
        // Explicit execution-owner loop; never called from read-only snapshots.
        public void ReconcileControlledV3()
        {
            lock(controlledSync)
            {
                if(controlledObservationOnly) return;
                if(controlledOperation==null) return;
                DrainControlledCallbacks();
                List<Execution> executions; List<Order> orders;
                lock(selectedAccount.Executions) executions=selectedAccount.Executions.Where(e=>e.Order!=null && e.Order.Instrument!=null && e.Order.Instrument.FullName==InstrumentName).ToList();
                foreach(var execution in executions)
                    if(!controlledOperation.IsBaselineExecution(execution.ExecutionId)) ControlledExecutionCallback(execution,true);
                lock(selectedAccount.Orders) orders=selectedAccount.Orders.Where(o=>controlledOperation.RoleForName(o.Name)!=null).ToList();
                foreach(var order in orders) ControlledOrderCallback(order,true);
                DrainControlledCallbacks();
                foreach(string path in Directory.GetFiles(controlledReceiptDirectory,"*.receipt.json").OrderBy(p=>p,StringComparer.Ordinal))
                {
                    var receipt=ControlledJson(path);
                    string receiptAdmission=ControlledText(receipt,"admission_digest"), executionDigest=ControlledText(receipt,"executions_digest"),
                        checkpointDigest=ControlledText(receipt,"checkpoint_digest"), authenticator=ControlledText(receipt,"authenticator");
                    string signed=receiptAdmission+"\n"+executionDigest+"\n"+checkpointDigest+"\n";
                    if(!new HashSet<string>(new[]{"admission_digest","executions_digest","checkpoint_digest","authenticator"}).SetEquals(receipt.Keys) ||
                        receiptAdmission!=controlledAdmission.Digest ||
                        !System.Text.RegularExpressions.Regex.IsMatch(executionDigest,@"\A[0-9a-f]{64}\z") ||
                        !System.Text.RegularExpressions.Regex.IsMatch(checkpointDigest,@"\A[0-9a-f]{64}\z") ||
                        !ControlledAdmissionV3.Equal(authenticator,ControlledAdmissionV3.Mac(controlledKey,Encoding.UTF8.GetBytes("arms.native.financial.v3\0"+signed))))
                    { controlledOperation.UnassignedEvidence(); throw new InvalidDataException("Unverifiable financial receipt."); }
                    try { controlledOperation.FinancialApplied(ControlledText(receipt,"admission_digest"),ControlledText(receipt,"executions_digest"),
                        ControlledText(receipt,"checkpoint_digest"),ControlledText(receipt,"authenticator")); }
                    catch(InvalidDataException) { /* Older execution-set receipts cannot attest the current phase. */ }
                }
                controlledOperation.Tick();
            }
        }
        private void DisposeControlledV3()
        {
            lock(controlledSync)
            {
                controlledServiceStopped=true;
                if(controlledServiceTimer!=null) {controlledServiceTimer.Stop();controlledServiceTimer.Tick-=OnControlledService;}
                if(controlledOperation!=null) controlledOperation.Dispose();
                if(controlledKey!=null) Array.Clear(controlledKey,0,controlledKey.Length);
            }
        }
        private sealed class ControlledAccountAdapter : IControlledAccountV3
        {
            private readonly ArmsSimNativeSubmitBridgeV2 owner;
            internal ControlledAccountAdapter(ArmsSimNativeSubmitBridgeV2 owner) { this.owner=owner; }
            public ControlledSnapshotV3 Snapshot() { return owner.ControlledSnapshot(); }
            public object Create(ControlledOrderV3 order) { return owner.CreateControlledOrder(order); }
            public void Submit(object order) { owner.SubmitControlledOrder(order); }
            public void SubmitProtection(object stop,object target) {owner.SubmitControlledProtection(stop,target);}
            public void Cancel(string[] names) { owner.CancelControlledOrders(names); }
        }
    }
}
