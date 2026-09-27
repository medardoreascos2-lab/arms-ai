// Synthetic-only call recorder: no NinjaTrader assemblies or account handles.
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Web.Script.Serialization;
using Arms.NativeSim;

internal sealed class RecordingAccount : IControlledAccountV3
{
    internal ControlledSnapshotV3 State;
    internal readonly List<ControlledOrderV3> Orders=new List<ControlledOrderV3>();
    internal readonly string Calls;
    internal int Queries;
    internal bool FailCreate, FailSubmit;
    internal RecordingAccount(string root,long now)
    {
        Calls=Path.Combine(root,"calls.txt");
        State=new ControlledSnapshotV3 { Account="Sim101",Provider="Simulator",Instrument="NQ DEC26",
            Generation=1,RiskVersion="risk-v1",ObservedUs=now,Connected=true,PositionQuantity=0,
            PositionSide="BUY",ActiveOrderNames=new string[0] };
        State.AccountClaims=new JavaScriptSerializer().Deserialize<Dictionary<string,string>>(
            File.ReadAllText(Path.Combine(root,"expected.binding.json")));
    }
    private void Record(string text) { File.AppendAllText(Calls,text+"\n"); }
    public ControlledSnapshotV3 Snapshot() { Queries++;return State; }
    public object Create(ControlledOrderV3 order)
    { Record("CREATE "+order.Role);if(FailCreate) throw new IOException("synthetic uncertain create");Orders.Add(order);return order; }
    public void Submit(object order)
    {
        var spec=(ControlledOrderV3)order; Record("SUBMIT "+spec.Role);
        if(FailSubmit) throw new IOException("synthetic uncertain submit");
        State.ActiveOrderNames=State.ActiveOrderNames.Concat(new[]{spec.Name}).ToArray();
    }
    public void Cancel(string[] names) { Record("CANCEL"); }
    public void Flatten(string instrument) { Record("FLATTEN"); }
}

internal static class ControlledSimHarness
{
    static int Main(string[] args)
    {
        string mode=args[0], root=args[1];long now=2000000000000000L;
        var account=new RecordingAccount(root,now); ControlledOperationV3 operation=null;
        account.FailCreate=mode=="create_failure"; account.FailSubmit=mode=="submit_failure";
        string error="",status="";
        try
        {
            byte[] key=File.ReadAllBytes(Path.Combine(root,"key.bin"));
            var admission=ControlledAdmissionV3.Read(File.ReadAllBytes(Path.Combine(root,"input.admission")),key);
            if(mode=="account") account.State.Account="Other";
            if(mode=="provider") account.State.Provider="Other";
            if(mode=="instrument") account.State.Instrument="MNQ DEC26";
            if(mode=="generation") account.State.Generation=2;
            if(mode=="risk_version") account.State.RiskVersion="other";
            if(mode=="nonflat") account.State.PositionQuantity=1;
            if(mode=="active_order") account.State.ActiveOrderNames=new[]{"unrelated"};
            if(mode=="disconnected") account.State.Connected=false;
            if(mode=="stale_snapshot") account.State.ObservedUs=now-16000000;
            operation=new ControlledOperationV3(admission,account,()=>now,key,Path.Combine(root,"state"),"NQ DEC26");
            if(mode.StartsWith("crash_")) operation.AfterPersist=p=>{if(p==mode.Substring(6)) Environment.Exit(86);};
            operation.Enter(mode=="command_id"?"other":admission["command_id"],mode=="command_digest"?"other":admission.Digest,
                mode=="activation_id"?"other":admission["activation_id"],mode=="activation_digest"?"other":admission.Digest,
                mode!="missing_activation",mode=="consumed_activation",mode!="disabled",()=>File.WriteAllText(Path.Combine(root,"consumed"),"1"));
            if(mode=="entry_only") return Print(account,operation.Status,error);
            if(mode=="entry_rejected" || mode=="entry_cancelled")
            {operation.OrderUpdate("ENTRY",mode=="entry_rejected"?"Rejected":"Cancelled","entry-native");return Print(account,operation.Status,error);}
            if(mode=="partial_label")
            {operation.OrderUpdate("ENTRY","PartFilled","entry-native");return Print(account,operation.Status,error);}
            if(mode=="lagging_partial") operation.OrderUpdate("ENTRY","PartFilled","entry-native");
            account.State.ActiveOrderNames=new string[0]; account.State.PositionQuantity=1;
            decimal price=mode=="adverse"?101m:mode=="invalid_stop"?89m:100m;
            operation.Execution("ENTRY","exec-entry",mode=="fractional"?0.5m:mode=="overfill"?2m:1m,price,"entry-native");
            if(mode=="duplicate") operation.Execution("ENTRY","exec-entry",1m,price,"entry-native");
            if(mode=="conflict") operation.Execution("ENTRY","exec-entry",1m,price+1,"entry-native");
            if(mode=="second_execution") operation.Execution("ENTRY","different-exec",1m,price,"entry-native");
            if(mode=="stop_rejected") operation.OrderUpdate("PROTECTIVE_STOP","Rejected","stop-native");
            if(mode=="target_rejected") operation.OrderUpdate("PROFIT_TARGET","Rejected","target-native");
            if(mode=="protected" || mode=="target_fill" || mode=="stop_fill" || mode=="reordered")
            {
                operation.OrderUpdate("PROTECTIVE_STOP","Working","stop-native");
                operation.OrderUpdate("PROFIT_TARGET","Accepted","target-native");
            }
            if(mode=="reordered") operation.OrderUpdate("PROTECTIVE_STOP","Submitted","stop-native");
            if(mode=="target_fill" || mode=="stop_fill")
            {
                string role=mode=="target_fill"?"PROFIT_TARGET":"PROTECTIVE_STOP";
                operation.Execution(role,"exec-exit",1m,mode=="target_fill"?120m:90m,mode=="target_fill"?"target-native":"stop-native");
                account.State.PositionQuantity=0;
                account.State.ActiveOrderNames=new[]{operation.OrderName(mode=="target_fill"?"PROTECTIVE_STOP":"PROFIT_TARGET")};
                operation.Tick();
            }
            if(mode=="timeout" || mode=="cancel_race" || mode=="duplicate_recovery" || mode=="already_flat" || mode=="recovery_disconnect")
            {
                now+=1000001;account.State.ObservedUs=now;
                operation.Tick(); // cancellation requested; never infer acknowledgement
                operation.Tick();
                if(mode=="recovery_disconnect") account.State.Connected=false;
                if(mode=="already_flat") account.State.PositionQuantity=0;
                account.State.ActiveOrderNames=new string[0];
                if(mode=="cancel_race") operation.Tick(); // Missing terminal proof requires reconciliation, never a guessed close.
                operation.OrderUpdate("PROTECTIVE_STOP","Cancelled","stop-native");
                operation.OrderUpdate("PROFIT_TARGET","Cancelled","target-native");
                operation.Tick();operation.Tick();
            }
            if(mode=="adverse" || mode=="invalid_stop") {operation.Tick();operation.Tick();}
            status=operation.Status;
        }
        catch(Exception e) { error=e.GetType().Name+": "+e.Message; status=operation==null?"REJECTED":operation.Status; }
        finally { if(operation!=null) operation.Dispose(); }
        return Print(account,status,error);
    }
    static int Print(RecordingAccount account,string status,string error)
    {
        string[] calls=File.Exists(account.Calls)?File.ReadAllLines(account.Calls):new string[0];
        Console.WriteLine(new JavaScriptSerializer().Serialize(new {classification="SYNTHETIC_OFFLINE_SIM_V3",status,error,
            create=calls.Count(c=>c.StartsWith("CREATE")),submit=calls.Count(c=>c.StartsWith("SUBMIT")),
            cancel=calls.Count(c=>c=="CANCEL"),flatten=calls.Count(c=>c=="FLATTEN"),queries=account.Queries,
            orders=account.Orders.Select(o=>new{role=o.Role,price=o.Price,oco=o.Oco,action=o.Action,quantity=o.Quantity,instrument=o.Instrument}).ToArray()}));
        return 0;
    }
}
