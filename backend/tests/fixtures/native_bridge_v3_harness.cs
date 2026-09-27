// Synthetic SDK only. This executable does not reference NinjaTrader assemblies.
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Web.Script.Serialization;
using NinjaTrader.Cbi;
using Arms.NativeSim;
namespace System.Windows.Threading
{
    // Inert offline dispatcher timer. Tests explicitly drive reconciliation.
    public sealed class DispatcherTimer {public TimeSpan Interval;public event EventHandler Tick;public void Start() {} public void Stop() {}}
}
namespace NinjaTrader.Cbi
{
    public enum Provider { Simulator, Other }
    public enum ConnectionStatus { Connected, Disconnected }
    public enum MarketPosition { Flat, Long, Short }
    public enum OrderState { Initialized, Submitted, Accepted, Working, PartFilled, Filled, Cancelled, Rejected, CancelPending }
    public enum OrderAction { Buy, Sell, BuyToCover, SellShort }
    public enum OrderType { Market, StopMarket, Limit }
    public enum TimeInForce { Day }
    public sealed class Instrument
    {
        public string FullName;
        static Dictionary<string,Instrument> values=new Dictionary<string,Instrument>();
        public static Instrument GetInstrument(string name,bool ignored)
        { if(!values.ContainsKey(name)) values[name]=new Instrument {FullName=name}; return values[name]; }
    }
    public sealed class Position { public Instrument Instrument; public MarketPosition MarketPosition; public int Quantity; }
    public sealed class PositionEventArgs : EventArgs {public Position Position;}
    public sealed class Order
    {
        public Account Account; public Instrument Instrument; public string Name,OrderId,Oco;
        public int Quantity,Filled; public double AverageFillPrice,LimitPrice,StopPrice;
        public OrderState OrderState; public OrderAction OrderAction; public OrderType OrderType;
    }
    public sealed class Execution { public Account Account; public Order Order; public string ExecutionId; public int Quantity; public double Price; public Instrument Instrument {get{return Order==null?null:Order.Instrument;}} }
    public sealed class Account
    {
        public string Name="Sim101", Root; public Provider Provider=Provider.Simulator;
        public ConnectionStatus ConnectionStatus=ConnectionStatus.Connected;
        public List<Order> Orders=new List<Order>(); public List<Position> Positions=new List<Position>(); public List<Execution> Executions=new List<Execution>();
        public int Creates,Submits,Cancels,Flattens; public bool FailCreate,FailSubmit,CloseDuringRecoveryCreate;
        public Action<Order> OnSubmit,OnCreate;
        void Log(string value) {File.AppendAllText(Path.Combine(Root,"sdk.calls"),value+"\n");}
        public Order CreateOrder(Instrument instrument,OrderAction action,OrderType type,TimeInForce tif,int qty,double limit,double stop,string oco,string name,object unused)
        {
            Creates++;Log("CREATE "+name);if(FailCreate) throw new IOException("synthetic uncertain create");
            var order=new Order {Account=this,Instrument=instrument,OrderAction=action,OrderType=type,Quantity=qty,LimitPrice=limit,StopPrice=stop,Oco=oco,Name=name,OrderId="native-"+name,OrderState=OrderState.Initialized};
            Orders.Add(order);if(CloseDuringRecoveryCreate && name.EndsWith(".R")) Positions.Clear();if(OnCreate!=null) OnCreate(order);return order;
        }
        public void Submit(IEnumerable<Order> values) {var orders=values.ToArray(); Submits++;Log("SUBMIT "+string.Join("|",orders.Select(o=>o.Name)));if(FailSubmit) throw new IOException("synthetic uncertain submit");foreach(var order in orders) {order.OrderState=OrderState.Submitted;if(OnSubmit!=null) OnSubmit(order);} }
        public void Cancel(ICollection<Order> orders) { Cancels++;Log("CANCEL");foreach(var order in orders) order.OrderState=OrderState.CancelPending; }
        public void Flatten(ICollection<Instrument> instruments) {Flattens++;Log("FLATTEN");}
    }
}
namespace NinjaTrader.NinjaScript.Indicators
{
    // Replaces only the platform host shell. SDK binding/model are production
    // source. The synthetic switch cannot change the committed bridge constant.
    public partial class ArmsSimNativeSubmitBridgeV2
    {
        public sealed class SyntheticDispatcher {public void InvokeAsync(Action action) {}}
        public sealed class SyntheticChart {public SyntheticDispatcher Dispatcher=new SyntheticDispatcher();}
        public SyntheticChart ChartControl=new SyntheticChart();
        public static bool SyntheticEnabled=true;
        private bool NATIVE_SUBMIT_ENABLED {get{return SyntheticEnabled;}}
        private const bool NATIVE_EMERGENCY_FLATTEN_ENABLED=true;
        private const string REQUIRED_ARM_TOKEN="ARM_SIM_ONE_SHOT_V2";
        private const string EMERGENCY_FLATTEN_ARM_TOKEN="ARM_SIM_EMERGENCY_FLATTEN_V2";
        private Account selectedAccount; private bool submitAttempted,emergencyFlattenAttempted,emergencyFlattenAwaitingConfirmation;
        private string emergencyFlattenInstrumentName;
        public string CommandDirectory,ActivationDirectory,InstrumentName="NQ DEC26",Side="BUY",CommandId="command-id",OperatorArmToken=REQUIRED_ARM_TOKEN;
        public string SelectedAccountName="Sim101",EmergencyFlattenArmToken=EMERGENCY_FLATTEN_ARM_TOKEN;
        public string EmergencyActivationDirectory,EmergencyActivationId="synthetic-manual-operation";
        public bool RequestOneShotSubmit=true,RequestEmergencyFlatten; public int Quantity=1;
        private void ValidateSelectedAccount() {if(selectedAccount.Name!="Sim101" || selectedAccount.Provider!=Provider.Simulator) throw new InvalidDataException("wrong native identity");}
        private void ReadEmergencyFlattenActivation(Instrument instrument) { }
        private void ConsumeEmergencyFlattenActivation() { }
        private void Print(string message) { }
        public string Status {get{return controlledOperation==null?"NONE":controlledOperation.Status;}}
        public void SetAccount(Account account) {selectedAccount=account;EmergencyActivationDirectory=Path.Combine(account.Root,"activation");}
        public void Start() {AttemptControlledV3();}
        public void Feed(Order order) {ControlledOrderCallback(order);}
        public void Feed(Execution execution) {ControlledExecutionCallback(execution);}
        public void Enqueue(Order order) {QueueControlledOrder(order);}
        public void Enqueue(Execution execution) {QueueControlledExecution(execution);}
        public void Close() {DisposeControlledV3();}
        public void CrashAt(string phase) {controlledOperation.AfterPersist=p=>{if(p==phase) Environment.Exit(86);};}
        public void ManualStart() {RequestEmergencyFlatten=true;AttemptEmergencyFlatten();}
        public void ManualAdvance() {AdvanceManualEmergencyRecovery();}
        public void PositionCallback(Position position) {OnNativePositionUpdate(selectedAccount,new PositionEventArgs {Position=position});OnControlledService(null,EventArgs.Empty);}
        public bool ManualPending {get{return emergencyFlattenAwaitingConfirmation;}}
        public void ForceFence() {controlledOperation.UnassignedEvidence();}
        public void CheckMutationGuard() {ControlledMutationGuard();}
    }
}
internal static class NativeBridgeHarness
{
    static void ConfigureManual(NinjaTrader.NinjaScript.Indicators.ArmsSimNativeSubmitBridgeV2 bridge,string root,Func<long> clock)
    {
        var claims=new JavaScriptSerializer().Deserialize<Dictionary<string,string>>(File.ReadAllText(Path.Combine(root,"claims.json")));
        bridge.ConfigureControlledV3(File.ReadAllBytes(Path.Combine(root,"key.bin")),claims,1,"risk-v1",Path.Combine(root,"state"),Path.Combine(root,"receipts"),clock);
    }
    static Dictionary<string,string> Permit(Dictionary<string,string> context,long now)
    {var permit=new Dictionary<string,string>(context);permit["nonce"]=Guid.NewGuid().ToString("N");permit["issued_us"]=now.ToString(CultureInfo.InvariantCulture);permit["expires_us"]=(now+1000000).ToString(CultureInfo.InvariantCulture);return permit;}
    static string Sign(Dictionary<string,string> permit,string root)
    {return ControlledAdmissionV3.Mac(File.ReadAllBytes(Path.Combine(root,"key.bin")),System.Text.Encoding.UTF8.GetBytes("arms.native.operator-reconciliation.v3\0").Concat(OperatorReconciliationV3.Canonical(permit)).ToArray());}
    static void ReconcileOperator(NinjaTrader.NinjaScript.Indicators.ArmsSimNativeSubmitBridgeV2 bridge,string root,long now)
    {var permit=Permit(bridge.ControlledReconciliationContextV3(),now);bridge.ApplyControlledReconciliationV3(permit,Sign(permit,root),"ARM_SIM_RECONCILIATION_V3");}
    static Execution Fill(Account account,Order order,string id,double price,int quantity=1)
    {
        order.Filled=quantity;order.OrderState=OrderState.Filled;order.AverageFillPrice=price;
        account.Positions.Clear();
        if(order.Name.EndsWith(".E")) account.Positions.Add(new Position {Instrument=order.Instrument,MarketPosition=order.OrderAction==OrderAction.Buy?MarketPosition.Long:MarketPosition.Short,Quantity=quantity});
        var execution=new Execution {Account=account,Order=order,ExecutionId=id,Price=price,Quantity=quantity}; account.Executions.Add(execution);return execution;
    }
    static int Main(string[] args)
    {
        string root=args[0],mode=args[1],error=""; long now=2000000000000000L;
        var account=new Account {Root=root};
        if(mode.StartsWith("restore"))
        {
            now+=2000000;
            var saved=new JavaScriptSerializer().Deserialize<SavedAccount>(File.ReadAllText(Path.Combine(root,"sdk.snapshot.json")));
            foreach(var row in saved.orders)
                account.Orders.Add(new Order {Account=account,Instrument=Instrument.GetInstrument(row.instrument,true),Name=row.name,OrderId=row.id,Quantity=row.quantity,Filled=row.filled,
                    OrderState=(OrderState)Enum.Parse(typeof(OrderState),row.state),OrderAction=(OrderAction)Enum.Parse(typeof(OrderAction),row.action),OrderType=(OrderType)Enum.Parse(typeof(OrderType),row.type),
                    LimitPrice=row.limit,StopPrice=row.stop,Oco=row.oco});
            foreach(var row in saved.executions)
                account.Executions.Add(new Execution {Account=account,Order=account.Orders.Single(o=>o.OrderId==row.order),ExecutionId=row.id,Quantity=row.quantity,Price=row.price});
            foreach(var row in saved.positions)
                account.Positions.Add(new Position {Instrument=Instrument.GetInstrument(row.instrument,true),Quantity=row.quantity,MarketPosition=(MarketPosition)Enum.Parse(typeof(MarketPosition),row.side)});
        }
        var bridge=new NinjaTrader.NinjaScript.Indicators.ArmsSimNativeSubmitBridgeV2 {CommandDirectory=Path.Combine(root,"spool","commands"),ActivationDirectory=Path.Combine(root,"activation")};
        bridge.SetAccount(account);
        if(mode=="restore_manual")
        {
            ConfigureManual(bridge,root,()=>now);bridge.ManualStart();bridge.ManualAdvance();
            return Report(account,bridge,error);
        }
        if(mode=="b3_terminal_fill_delayed_position")
        {
            ConfigureManual(bridge,root,()=>now);
            var order=account.CreateOrder(Instrument.GetInstrument("NQ DEC26",true),OrderAction.Buy,OrderType.Market,TimeInForce.Day,1,0,0,"","manual-terminal",null);
            order.OrderState=OrderState.Filled;order.Filled=1;
            account.Executions.Add(new Execution {Account=account,Order=order,ExecutionId="terminal-before-position",Quantity=1,Price=100});
            bridge.ManualStart(); // Position inventory still carries the older FLAT observation.
            bool pendingBeforePosition=bridge.ManualPending;
            account.Positions.Add(new Position {Instrument=order.Instrument,MarketPosition=MarketPosition.Long,Quantity=1});
            bridge.PositionCallback(account.Positions[0]);
            Console.WriteLine(new JavaScriptSerializer().Serialize(new {pending_before_position=pendingBeforePosition,
                pending_after_position=bridge.ManualPending,remaining_quantity=account.Positions[0].Quantity,
                cancel=account.Cancels,flatten=account.Flattens}));
            bridge.Close();return 0;
        }
        if(mode.StartsWith("manual_"))
        {
            ConfigureManual(bridge,root,()=>now);
            var order=account.CreateOrder(Instrument.GetInstrument("NQ DEC26",true),OrderAction.Buy,OrderType.Market,TimeInForce.Day,1,0,0,"","manual",null);
            if(mode=="manual_unsettled_baseline")
            { order.Filled=1;account.Executions.Add(new Execution {Account=account,Order=order,ExecutionId="pre-cancel-fill",Quantity=1,Price=100}); }
            bridge.ManualStart(); // initially FLAT with a live order; must wait.
            if(account.Flattens!=0 || !bridge.ManualPending) throw new Exception("stale-flat completion");
            order.OrderState=OrderState.Cancelled;
            if(mode=="manual_cancel_fill" || mode=="manual_lagging_position")
            {
                order.Filled=1;
                account.Positions.Add(new Position {Instrument=order.Instrument,MarketPosition=MarketPosition.Long,Quantity=1});
                bridge.ManualAdvance();if(account.Flattens!=0) throw new Exception("unreconciled fill");
                account.Executions.Add(new Execution {Account=account,Order=order,ExecutionId="manual-fill",Quantity=1,Price=100});
                if(mode=="manual_lagging_position")
                {
                    account.Positions.Clear();bridge.ManualAdvance();
                    if(account.Flattens!=0 || !bridge.ManualPending) throw new Exception("lagging position accepted");
                    account.Positions.Add(new Position {Instrument=order.Instrument,MarketPosition=MarketPosition.Long,Quantity=1});
                }
            }
            bridge.ManualAdvance();bridge.ManualAdvance();
            if(mode!="manual_unsettled_baseline" && mode!="manual_no_permit")
            {var permit=Permit(bridge.ManualReconciliationContextV3(),now);bridge.ApplyManualReconciliationV3(permit,Sign(permit,root),"ARM_SIM_RECONCILIATION_V3");}
            if(mode=="manual_unsettled_baseline" && !bridge.ManualPending) throw new Exception("unproven baseline declared complete");
            return Report(account,bridge,error);
        }
        try
        {
            var claims=new JavaScriptSerializer().Deserialize<Dictionary<string,string>>(File.ReadAllText(Path.Combine(root,"claims.json")));
            if(mode=="wrong_backend") claims["backend_account_id"]="SIM_NATIVE-00000000000000000000000000000000";
            if(mode=="wrong_risk") claims["risk_profile_id"]="OTHER";
            if(mode=="wrong_account") account.Name="Other";
            if(mode=="wrong_provider") account.Provider=Provider.Other;
            if(mode=="wrong_instrument") bridge.InstrumentName="MNQ DEC26";
            if(mode=="short_recovery") bridge.Side="SELL";
            if(mode=="nonflat") account.Positions.Add(new Position {Instrument=Instrument.GetInstrument("NQ DEC26",true),MarketPosition=MarketPosition.Long,Quantity=1});
            if(mode=="active") account.Orders.Add(new Order {Instrument=Instrument.GetInstrument("NQ DEC26",true),Name="unrelated"});
            if(mode=="expired") now+=16000000;
            if(mode=="disabled") NinjaTrader.NinjaScript.Indicators.ArmsSimNativeSubmitBridgeV2.SyntheticEnabled=false;
            if(mode=="async_callbacks") account.OnSubmit=order=> {
                var callback=new System.Threading.Thread(()=>bridge.Enqueue(order));callback.IsBackground=true;callback.Start();
                if(!callback.Join(2000)) throw new Exception("SDK callback deadlocked on operation owner");
            };
            bridge.ConfigureControlledV3(File.ReadAllBytes(Path.Combine(root,"key.bin")),claims,1,"risk-v1",Path.Combine(root,"state"),Path.Combine(root,"receipts"),()=>now);
            if(mode.StartsWith("restore"))
            {
                bridge.RestoreControlledV3();
                if(mode.StartsWith("restore_crash_")) bridge.CrashAt(mode.Substring(14));
                bridge.ReconcileControlledV3();bridge.ReconcileControlledV3();
                if((mode=="restore_reconciled" || mode.StartsWith("restore_crash_")) && bridge.Status!="RECOVERY_COMPLETE") ReconcileOperator(bridge,root,now);
                return Report(account,bridge,error);
            }
            bridge.Start();
            if(mode=="entry") return Report(account,bridge,error);
            if(mode.StartsWith("crash_")) bridge.CrashAt(mode.Substring(6));
            var entry=account.Orders.Single(o=>o.Name.EndsWith(".E"));
            if(mode=="b1_exit_during_create") account.OnCreate=order=> {
                if(order.Name.EndsWith(".S")) bridge.Enqueue(Fill(account,order,"exit-during-create",90));
            };
            if(mode=="b1_stop_fill_during_submit" || mode=="b1_target_fill_during_submit") account.OnSubmit=order=> {
                if(order.Name.EndsWith(mode=="b1_stop_fill_during_submit"?".S":".T")) bridge.Enqueue(Fill(account,order,"exit-during-submit",mode=="b1_stop_fill_during_submit"?90:120));
            };
            if(mode=="b2_unknown_before_entry")
            {
                var unknown=new Order {Account=account,Instrument=entry.Instrument,Name="Flatten",OrderId="unassigned",Quantity=1};
                bridge.Feed(new Execution {Account=account,Order=unknown,ExecutionId="unknown-before-entry",Quantity=1,Price=100});
                if(bridge.Status!="RECONCILIATION_REQUIRED") throw new Exception("ambiguous execution did not raise initial fence");
            }
            if(mode=="rejected" || mode=="cancelled" || mode=="flat_permit_twice" || mode=="flat_permit_late_fill")
            {
                entry.OrderState=mode=="rejected"?OrderState.Rejected:OrderState.Cancelled;bridge.Feed(entry);
                if(mode.StartsWith("flat_permit_"))
                {
                    var permit=Permit(bridge.ControlledReconciliationContextV3(),now);string signature=Sign(permit,root);bridge.ApplyControlledReconciliationV3(permit,signature,"ARM_SIM_RECONCILIATION_V3");
                    if(mode=="flat_permit_late_fill") bridge.Feed(Fill(account,entry,"late-entry",100));
                    else bridge.ApplyControlledReconciliationV3(permit,signature,"ARM_SIM_RECONCILIATION_V3");
                }
                return Report(account,bridge,error);
            }
            var fill=Fill(account,entry,"exec-entry",mode=="adverse"?101:100,mode=="overfill"?2:1);
            if(mode=="b1_already_flat") account.Positions.Clear();
            bridge.Feed(fill);
            if(mode.StartsWith("b1_") || mode=="b2_unknown_before_entry") return Report(account,bridge,error);
            if(mode=="duplicate") bridge.Feed(fill);
            if(mode=="unknown" || mode=="spoof_order") {var foreign=new Order {Account=account,Instrument=entry.Instrument,Name=mode=="unknown"?"Flatten":entry.Name.Replace(".E",".R"),OrderId="unassigned",Quantity=1};bridge.Feed(new Execution {Account=account,Order=foreign,ExecutionId="unassigned",Quantity=1,Price=100});return Report(account,bridge,error);}
            if(mode=="protected" || mode=="duplicate" || mode=="async_callbacks")
            {foreach(var order in account.Orders.Where(o=>!o.Name.EndsWith(".E"))) {order.OrderState=OrderState.Working;bridge.Feed(order);}return Report(account,bridge,error);}
            if(mode=="adverse") {bridge.ReconcileControlledV3();ReconcileOperator(bridge,root,now);return Report(account,bridge,error);}
            if(mode=="overfill") return Report(account,bridge,error);
            var stop=account.Orders.Single(o=>o.Name.EndsWith(".S"));var target=account.Orders.Single(o=>o.Name.EndsWith(".T"));
            if(mode.StartsWith("b2_fenced_"))
            {
                bridge.ForceFence();
                if(mode.EndsWith("stop") || mode.EndsWith("target")) bridge.Feed(Fill(account,mode.EndsWith("stop")?stop:target,"exit-fenced",90));
                bridge.Feed(fill);bridge.Feed(fill);stop.OrderState=OrderState.Working;bridge.Feed(stop);target.OrderState=OrderState.Working;bridge.Feed(target);
                bridge.ReconcileControlledV3();
                if(mode.EndsWith("guard")) bridge.CheckMutationGuard();
                return Report(account,bridge,error);
            }
            if(mode=="target" || mode=="stop")
            {var exit=mode=="target"?target:stop;bridge.Feed(Fill(account,exit,"exec-exit",mode=="target"?120:90));bridge.ReconcileControlledV3();var sibling=mode=="target"?stop:target;sibling.OrderState=OrderState.Cancelled;bridge.Feed(sibling);bridge.ReconcileControlledV3();return Report(account,bridge,error);}
            now+=1000001;bridge.ReconcileControlledV3(); // timed out; cancellation is not completion.
            if(mode=="unresolved") {account.Orders.Remove(stop);account.Orders.Remove(target);bridge.ReconcileControlledV3();return Report(account,bridge,error);}
            if(mode=="cancel_fill") {bridge.Feed(Fill(account,target,"exec-target-during-cancel",120));}
            else target.OrderState=OrderState.Cancelled;
            stop.OrderState=OrderState.Cancelled;bridge.Feed(stop);bridge.Feed(target);
            if(mode=="stale_flat") account.Positions.Clear();
            if(mode=="wrong_recovery_side") account.Positions[0].MarketPosition=MarketPosition.Short;
            if(mode=="wrong_recovery_qty") account.Positions[0].Quantity=2;
            if(mode=="recovery_create_failure") account.FailCreate=true;
            if(mode=="recovery_submit_failure") account.FailSubmit=true;
            if(mode=="close_during_create") account.CloseDuringRecoveryCreate=true;
            if(mode=="exit_during_recovery_create") account.OnCreate=order=> {
                if(order.Name.EndsWith(".R")) bridge.Enqueue(Fill(account,target,"late-exit",120));
            };
            if(mode=="expiry_during_create") account.OnCreate=order=> {if(order.Name.EndsWith(".R")) now+=2000000;};
            if(mode=="disabled_recovery") NinjaTrader.NinjaScript.Indicators.ArmsSimNativeSubmitBridgeV2.SyntheticEnabled=false;
            bridge.ReconcileControlledV3();bridge.ReconcileControlledV3();
            if(mode.StartsWith("permit_"))
            {
                if(mode=="permit_ambiguous") bridge.ForceFence();
                var permit=Permit(bridge.ControlledReconciliationContextV3(),now);
                string field=mode.Substring(7);
                if(permit.ContainsKey(field)) permit[field]="wrong";
                if(mode=="permit_expired") permit["expires_us"]=now.ToString(CultureInfo.InvariantCulture);
                if(mode=="permit_future") permit["issued_us"]=(now+1).ToString(CultureInfo.InvariantCulture);
                if(mode=="permit_stale_position") account.Positions.Clear();
                if(mode=="permit_disconnect") account.ConnectionStatus=ConnectionStatus.Disconnected;
                if(mode=="permit_replay") OperatorReconciliationV3.Consume(permit,Sign(permit,root),bridge.ControlledReconciliationContextV3(),File.ReadAllBytes(Path.Combine(root,"key.bin")),now,Path.Combine(root,"state"));
                if(mode=="permit_new_evidence") bridge.Feed(fill);
                bridge.ApplyControlledReconciliationV3(permit,mode=="permit_signature"?new string('0',64):Sign(permit,root),mode=="permit_token"?"wrong":"ARM_SIM_RECONCILIATION_V3");
                if(mode=="permit_double") bridge.ApplyControlledReconciliationV3(permit,Sign(permit,root),"ARM_SIM_RECONCILIATION_V3");
                return Report(account,bridge,error);
            }
            if(mode=="no_operator_disconnect") {account.ConnectionStatus=ConnectionStatus.Disconnected;bridge.ReconcileControlledV3();account.ConnectionStatus=ConnectionStatus.Connected;bridge.ReconcileControlledV3();}
            if(new[]{"recovery","recovery_fill","recovery_create_failure","recovery_submit_failure","close_during_create","exit_during_recovery_create","expiry_during_create","b2_recovery_callback","disabled_recovery","duplicate_entry","short_recovery","crash_POSITION_RECHECKED","crash_RECONCILIATION_PERMIT_CONSUMED","crash_OPERATOR_RECONCILED","crash_RECOVERY_CREATE_INTENT","crash_RECOVERY_CREATED","crash_RECOVERY_SUBMIT_INTENT","crash_RECOVERY_SUBMIT_RETURNED","crash_RECOVERY_NATIVE_EVIDENCE"}.Contains(mode))
                ReconcileOperator(bridge,root,now);
            if(mode=="b2_recovery_callback")
            {bridge.ForceFence();var close=account.Orders.Single(o=>o.Name.EndsWith(".R"));var exit=Fill(account,close,"exec-recovery",99);bridge.Feed(exit);bridge.Feed(exit);bridge.Feed(fill);bridge.ReconcileControlledV3();}
            if(mode=="duplicate_entry") bridge.Start();
            if(mode=="recovery_fill" || mode=="crash_RECOVERY_NATIVE_EVIDENCE")
            {var close=account.Orders.Single(o=>o.Name.EndsWith(".R"));var exit=Fill(account,close,"exec-recovery",99);bridge.Feed(exit);bridge.Feed(exit);bridge.ReconcileControlledV3();}
        }
        catch(Exception e) {error=e.GetType().Name+": "+e.Message;}
        finally {bridge.Close();}
        return Report(account,bridge,error);
    }
    static int Report(Account a,NinjaTrader.NinjaScript.Indicators.ArmsSimNativeSubmitBridgeV2 b,string error)
    {
        File.WriteAllText(Path.Combine(a.Root,"sdk.snapshot.json"),new JavaScriptSerializer().Serialize(new {
            orders=a.Orders.Select(o=>new {name=o.Name,id=o.OrderId,instrument=o.Instrument.FullName,quantity=o.Quantity,filled=o.Filled,state=o.OrderState.ToString(),action=o.OrderAction.ToString(),type=o.OrderType.ToString(),limit=o.LimitPrice,stop=o.StopPrice,oco=o.Oco}).ToArray(),
            executions=a.Executions.Select(e=>new {id=e.ExecutionId,order=e.Order.OrderId,quantity=e.Quantity,price=e.Price}).ToArray(),
            positions=a.Positions.Select(p=>new {instrument=p.Instrument.FullName,quantity=p.Quantity,side=p.MarketPosition.ToString()}).ToArray()}));
        Console.WriteLine(new JavaScriptSerializer().Serialize(new {error,status=b.Status,manual_pending=b.ManualPending,create=a.Creates,submit=a.Submits,cancel=a.Cancels,flatten=a.Flattens,
            orders=a.Orders.Select(o=>new {name=o.Name,quantity=o.Quantity,action=o.OrderAction.ToString(),type=o.OrderType.ToString(),limit=o.LimitPrice,stop=o.StopPrice,oco=o.Oco}).ToArray()}));return 0;
    }
    public sealed class SavedAccount {public SavedOrder[] orders;public SavedExecution[] executions;public SavedPosition[] positions;}
    public sealed class SavedOrder {public string name,id,instrument,state,action,type,oco;public int quantity,filled;public double limit,stop;}
    public sealed class SavedExecution {public string id,order;public int quantity;public double price;}
    public sealed class SavedPosition {public string instrument,side;public int quantity;}
}
