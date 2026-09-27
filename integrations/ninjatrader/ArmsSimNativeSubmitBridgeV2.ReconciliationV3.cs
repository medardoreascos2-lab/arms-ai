// Explicit operator reconciliation on the existing SDK owner. No automatic
// permit discovery, issuance, position-freshness inference, or native retry.
using System;
using System.Collections.Generic;
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
        private const string RECONCILIATION_ARM_TOKEN="ARM_SIM_RECONCILIATION_V3";
        private bool manualOperatorAuthorized;
        private string manualOperatorEvidence;
        private long manualOperatorDeadline;
        private string controlledReconciledExecutions,controlledReconciledRaw;
        private string ControlledExecutionSetDigest()
        {
            lock(selectedAccount.Executions)
                return OperatorReconciliationV3.Hash(Encoding.UTF8.GetBytes(string.Concat(selectedAccount.Executions
                    .Where(e=>e.Instrument!=null && e.Instrument.FullName==InstrumentName)
                    .Select(e=>e.ExecutionId+"|"+(e.Order==null?"":e.Order.OrderId+"|"+e.Order.Name)+"|"+e.Quantity.ToString(CultureInfo.InvariantCulture)+"|"+e.Price.ToString("R",CultureInfo.InvariantCulture))
                    .OrderBy(s=>s,StringComparer.Ordinal).Select(s=>s+"\n"))));
        }
        private string ManualFencePath()
        {
            string directory=string.IsNullOrWhiteSpace(EmergencyActivationDirectory)?controlledStateDirectory:EmergencyActivationDirectory;
            if(string.IsNullOrWhiteSpace(directory)) return null;
            if(!Path.IsPathRooted(directory) || !Directory.Exists(directory)) throw new InvalidDataException("Durable manual reconciliation directory required.");
            return Path.Combine(directory,"manual-reconciliation-"+OperatorReconciliationV3.Hash(Encoding.UTF8.GetBytes("Sim101|"+InstrumentName))+".pending");
        }
        private void RequireNoManualReconciliation()
        {
            string path=ManualFencePath();
            if(path!=null && File.Exists(path)) throw new InvalidOperationException("Durable manual reconciliation fence blocks new entries.");
        }
        private bool RestoreManualReconciliation()
        {
            string path=ManualFencePath();
            if(path==null || !File.Exists(path)) return false;
            emergencyFlattenAttempted=true;emergencyFlattenAwaitingConfirmation=true;
            emergencyFlattenInstrumentName=InstrumentName;manualOperatorAuthorized=false;
            manualFlattenIntent=File.Exists(path+".flatten-intent");
            if(controlledKey!=null && File.Exists(path+".complete"))
            {
                try
                {
                    var context=ManualContext();
                    var completion=new JavaScriptSerializer().Deserialize<Dictionary<string,string>>(File.ReadAllText(path+".complete",Encoding.UTF8));
                    string evidence=context["evidence_digest"];
                    if(context["position_quantity"]=="0" && context["unresolved_orders"]=="0" && context["execution_net"]=="0" &&
                        completion["evidence_digest"]==evidence && ControlledAdmissionV3.Equal(completion["authenticator"],
                        ControlledAdmissionV3.Mac(controlledKey,Encoding.UTF8.GetBytes("arms.native.manual-completion.v3\0"+evidence))))
                    {emergencyFlattenAwaitingConfirmation=false;return true;}
                }
                catch { /* Unverifiable completion remains fenced. */ }
            }
            Print("ARMS_SIM_EMERGENCY_RECONCILIATION_REQUIRED durable_fence");
            return true;
        }
        private void PersistManualReconciliation()
        {
            string path=ManualFencePath();
            if(path==null) throw new InvalidDataException("Manual recovery requires a durable reconciliation directory.");
            if(!File.Exists(path))
            {
                byte[] bytes=Encoding.UTF8.GetBytes(new JavaScriptSerializer().Serialize(new Dictionary<string,string> {
                    {"account","Sim101"},{"provider","Simulator"},{"instrument",InstrumentName},
                    {"operation_id",EmergencyActivationId},{"recovery_id",Guid.NewGuid().ToString("N")},
                    {"status","RECONCILIATION_REQUIRED"}}));
                using(var file=new FileStream(path,FileMode.CreateNew,FileAccess.Write,FileShare.None))
                {file.Write(bytes,0,bytes.Length);file.Flush(true);}
            }
            emergencyFlattenAwaitingConfirmation=true;manualOperatorAuthorized=false;
        }
        private string ControlledRawDigest()
        {
            return OperatorReconciliationV3.Hash(Encoding.UTF8.GetBytes(string.Concat(Directory.GetFiles(controlledStateDirectory,"raw-*.json")
                .OrderBy(p=>p,StringComparer.Ordinal).Select(p=>Path.GetFileName(p)+"|"+OperatorReconciliationV3.Hash(File.ReadAllBytes(p))+"\n"))));
        }
        public Dictionary<string,string> ControlledReconciliationContextV3()
        {
            lock(controlledSync)
            {
                if(controlledOperation==null || !controlledOperation.ReconciliationRequired) throw new InvalidOperationException("Persisted reconciliation fence required.");
                ReconcileControlledV3();
                if(controlledOperation==null) throw new InvalidOperationException("Controlled operation required.");
                var context=controlledOperation.ReconciliationContext(ControlledRawDigest());
                context["native_executions_digest"]=ControlledExecutionSetDigest();
                return context;
            }
        }
        public void ApplyControlledReconciliationV3(Dictionary<string,string> permit,string authenticator,string operatorToken)
        {
            lock(controlledSync)
            {
                if(operatorToken!=RECONCILIATION_ARM_TOKEN || controlledOperation==null || !controlledOperation.ReconciliationRequired) throw new InvalidOperationException("Explicit operator reconciliation required.");
                ReconcileControlledV3();
                string executions=ControlledExecutionSetDigest(),raw=ControlledRawDigest();
                controlledOperation.ApplyOperatorReconciliation(permit,authenticator,raw,executions);
                controlledReconciledExecutions=executions;controlledReconciledRaw=raw;
                controlledOperation.Tick();
            }
        }
        private Dictionary<string,string> ManualContext()
        {
            ValidateSelectedAccount();
            string path=ManualFencePath();
            if(path==null || !File.Exists(path) || controlledKey==null || controlledClaims==null || controlledGeneration<1 ||
                controlledOperation!=null || selectedAccount.ConnectionStatus!=ConnectionStatus.Connected)
                throw new InvalidDataException("Explicit configured manual reconciliation authority required.");
            var marker=new JavaScriptSerializer().Deserialize<Dictionary<string,string>>(File.ReadAllText(path,Encoding.UTF8));
            if(marker["account"]!="Sim101" || marker["provider"]!="Simulator" || marker["instrument"]!=InstrumentName)
                throw new InvalidDataException("Manual fence identity mismatch.");
            var values=new Dictionary<string,string>(controlledClaims);
            values["account"]="Sim101";values["provider"]="Simulator";values["instrument"]=InstrumentName;
            values["runtime_generation"]=controlledGeneration.ToString(CultureInfo.InvariantCulture);
            values["operation_id"]=marker["operation_id"];values["recovery_id"]=marker["recovery_id"];
            values["checkpoint_digest"]=OperatorReconciliationV3.Hash(File.ReadAllBytes(path));
            List<Execution> executions;List<Order> orders;List<Position> positions;
            lock(selectedAccount.Executions) executions=selectedAccount.Executions.Where(e=>e.Instrument!=null && e.Instrument.FullName==InstrumentName).ToList();
            lock(selectedAccount.Orders) orders=selectedAccount.Orders.Where(o=>o.Instrument!=null && o.Instrument.FullName==InstrumentName).ToList();
            lock(selectedAccount.Positions) positions=selectedAccount.Positions.Where(p=>p.Instrument!=null && p.Instrument.FullName==InstrumentName && p.MarketPosition!=MarketPosition.Flat).ToList();
            if(positions.Count>1) throw new InvalidDataException("Ambiguous manual position.");
            var executionRows=new SortedDictionary<string,string>(StringComparer.Ordinal);int net=0;
            foreach(var execution in executions)
            {
                if(execution.Order==null || !ReferenceEquals(execution.Account,selectedAccount) || !ReferenceEquals(execution.Order.Account,selectedAccount))
                    throw new InvalidDataException("Unassigned manual execution evidence.");
                int signed=ManualExecutionQuantity(execution);
                string row=execution.Order.OrderId+"|"+signed.ToString(CultureInfo.InvariantCulture)+"|"+execution.Price.ToString("R",CultureInfo.InvariantCulture);
                string prior;
                if(executionRows.TryGetValue(execution.ExecutionId,out prior)) {if(prior!=row) throw new InvalidDataException("Conflicting manual execution.");}
                else {executionRows.Add(execution.ExecutionId,row);net=checked(net+signed);}
            }
            int actual=positions.Count==0?0:positions[0].MarketPosition==MarketPosition.Long?positions[0].Quantity:-positions[0].Quantity;
            values["position_quantity"]=Math.Abs(actual).ToString(CultureInfo.InvariantCulture);
            values["position_side"]=actual==0?"FLAT":actual>0?"BUY":"SELL";
            values["execution_net"]=net.ToString(CultureInfo.InvariantCulture);
            values["executions_digest"]=OperatorReconciliationV3.Hash(Encoding.UTF8.GetBytes(string.Concat(executionRows.Select(p=>p.Key+"|"+p.Value+"\n"))));
            values["orders_digest"]=OperatorReconciliationV3.Hash(Encoding.UTF8.GetBytes(string.Concat(orders.OrderBy(o=>o.OrderId,StringComparer.Ordinal).Select(o=>o.OrderId+"|"+o.Name+"|"+o.OrderState+"|"+o.Filled+"|"+o.Quantity+"\n"))));
            values["unresolved_orders"]=orders.Count(o=>!ControlledTerminal(o.OrderState) || o.Filled!=executions.Where(e=>ReferenceEquals(e.Order,o)).GroupBy(e=>e.ExecutionId).Sum(g=>g.First().Quantity)).ToString(CultureInfo.InvariantCulture);
            values["evidence_digest"]=OperatorReconciliationV3.Hash(OperatorReconciliationV3.Canonical(values));
            return values;
        }
        public Dictionary<string,string> ManualReconciliationContextV3()
        {lock(manualEmergencySync) {RestoreManualReconciliation();return ManualContext();}}
        public void ApplyManualReconciliationV3(Dictionary<string,string> permit,string authenticator,string operatorToken)
        {
            lock(manualEmergencySync)
            {
                if(operatorToken!=RECONCILIATION_ARM_TOKEN) throw new InvalidOperationException("Explicit operator reconciliation required.");
                var expected=ManualContext();
                int net=int.Parse(expected["execution_net"],CultureInfo.InvariantCulture);
                int quantity=int.Parse(expected["position_quantity"],CultureInfo.InvariantCulture);
                if(expected["unresolved_orders"]!="0" || Math.Abs(net)!=quantity || quantity>1 ||
                    (net!=0 && expected["position_side"]!=(net>0?"BUY":"SELL")))
                    throw new InvalidDataException("Operator permit cannot resolve contradictory manual exposure.");
                OperatorReconciliationV3.Consume(permit,authenticator,expected,controlledKey,controlledClock(),Path.GetDirectoryName(ManualFencePath()));
                manualOperatorEvidence=expected["evidence_digest"];manualOperatorAuthorized=true;
                manualOperatorDeadline=long.Parse(permit["expires_us"],CultureInfo.InvariantCulture);
                manualExpectedPosition=net;manualKnownExecutions.Clear();manualBaselineUncertain=false;
                lock(selectedAccount.Executions)
                    foreach(var execution in selectedAccount.Executions.Where(e=>e.Order!=null && e.Order.Instrument!=null && e.Order.Instrument.FullName==InstrumentName))
                        manualKnownExecutions[execution.ExecutionId]=ManualExecutionQuantity(execution);
                emergencyFlattenAwaitingConfirmation=true;
                AdvanceManualEmergencyRecovery();
            }
        }
        private bool ManualReconciliationAllowsDecision()
        {
            if(!manualOperatorAuthorized || controlledClock==null || controlledClock()>=manualOperatorDeadline) return false;
            if(ManualContext()["evidence_digest"]!=manualOperatorEvidence) {manualOperatorAuthorized=false;return false;}
            return true;
        }
        private void CompleteManualReconciliation()
        {
            // Keep the deny marker and a durable completion receipt. A new entry
            // cannot silently reuse this manual recovery's filesystem namespace.
            string path=ManualFencePath()+".complete";
            using(var file=new FileStream(path,FileMode.CreateNew,FileAccess.Write,FileShare.None))
            {byte[] bytes=Encoding.UTF8.GetBytes(new JavaScriptSerializer().Serialize(new Dictionary<string,string> {
                {"evidence_digest",manualOperatorEvidence},{"authenticator",ControlledAdmissionV3.Mac(controlledKey,Encoding.UTF8.GetBytes("arms.native.manual-completion.v3\0"+manualOperatorEvidence))}}));
                file.Write(bytes,0,bytes.Length);file.Flush(true);}
            manualOperatorAuthorized=false;
        }
        private void PersistManualFlattenIntent()
        {
            using(var file=new FileStream(ManualFencePath()+".flatten-intent",FileMode.CreateNew,FileAccess.Write,FileShare.None))
            {byte[] bytes=Encoding.UTF8.GetBytes(manualOperatorEvidence);file.Write(bytes,0,bytes.Length);file.Flush(true);}
        }
    }
}
