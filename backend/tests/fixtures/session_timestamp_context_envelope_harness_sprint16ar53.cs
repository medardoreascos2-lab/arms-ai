// G integration: actual A-F1/G code, framework IO and F1's explicit SDK doubles.
// Compile with /main:ContextEnvelopeHarness. No native NinjaTrader assembly loaded.
using System;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using System.Security.Cryptography;
using System.Text;
using System.Threading;
using System.Web.Script.Serialization;
using Arms.AI.Diagnostics.R53;

internal static class ContextEnvelopeHarness
{
    static void Check(bool ok,string name) { if(!ok)throw new Exception(name); }
    static T Clone<T>(T value) { return (T)typeof(object).GetMethod("MemberwiseClone",BindingFlags.Instance|BindingFlags.NonPublic).Invoke(value,null); }
    static void Reject(Action action)
    { bool found=false;try { action(); }catch(ContextEnvelopeGuardException) { found=true; }Check(found,"EXPECTED_ENVELOPE_REJECTION"); }
    static string Fresh(string root,string name)
    { string result=Path.Combine(root,name+"-"+Guid.NewGuid().ToString("N"));Directory.CreateDirectory(result);return result; }
    static void Reset(string mode)
    {
        NinjaTrader.Cbi.Instrument.Next=new NinjaTrader.Cbi.Instrument();NinjaTrader.Cbi.Connection.PlaybackConnection=null;
        NinjaTrader.Core.Globals.GeneralOptions=new NinjaTrader.Core.Options();NinjaTrader.Data.TradingHours.Next=new NinjaTrader.Data.TradingHours();
        NinjaTrader.Data.BarsRequest.Last=null;NinjaTrader.Data.BarsRequest.TotalCreates=0;NinjaTrader.Data.BarsRequest.ThrowConstructor=false;
        NinjaTrader.Data.BarsRequest.ThrowConfiguration=false;NinjaTrader.Data.BarsRequest.AfterConstruct=null;NinjaTrader.Data.BarsRequest.NextMode=mode;
        if(mode=="irrelevant_exceptions")
        {
            var cal=NinjaTrader.Data.TradingHours.Next;
            cal.Holidays.Add(new DateTime(2026,1,1),"PRIVATE_PROVIDER_SENTINEL");
            cal.PartialHolidays.Add(new DateTime(2026,12,24),new NinjaTrader.Data.PartialHoliday { IsEarlyEnd=true,
                Constraint=new NinjaTrader.Data.Session { BeginDay=DayOfWeek.Thursday,EndDay=DayOfWeek.Thursday,TradingDay=DayOfWeek.Thursday } });
        }
    }
    sealed class Attempt
    {
        internal readonly object Owner=new object();internal readonly string Capture,Mode;
        internal readonly SessionTimestampLifecycleV1 Life;internal readonly SessionTimestampNativeContextV1 Context;
        internal SessionTimestampContextEnvelopeV1 Writer;internal SessionTimestampNativeRequestV1 Wrapped;
        internal NinjaTrader.Data.BarsRequest Raw;internal TimestampQueryPlan Plan;internal TimestampMatrixReport Report;
        internal bool Gates=true;
        internal Attempt(string folder,string mode)
        {
            Mode=mode;Capture=Path.Combine(folder,"capture");Directory.CreateDirectory(Capture);
            Life=new SessionTimestampLifecycleV1(Owner);
            Context=new SessionTimestampNativeContextV1(Owner,()=>new TimestampOperatorSettings(true,true,true,Gates,false,Capture),Capture);
        }
        internal void Start()
        {
            Life.Start(Owner,true,
                ()=> { Writer=new SessionTimestampContextEnvelopeV1(Owner,Life,Context,Capture,Guid.NewGuid().ToString("D"),Guid.NewGuid().ToString("D"),
                        Mode=="native_origin_claim"?"OPERATOR_NATIVE_RUN_UNATTESTED":"SYNTHETIC");return Writer; },
                ()=> {
                    Wrapped=Context.CreateAndWrap(Owner);Raw=(NinjaTrader.Data.BarsRequest)Wrapped.Identity;
                    Raw.AfterBars=()=> {
                        if(Mode=="mixed" || Mode=="duplicate" || Mode=="decreasing" || Mode=="misaligned")Raw.Bars.DataMode=Mode;
                        if(Mode=="rows4503")Raw.Bars.Count=4503;
                        if(Mode=="rows5520")Raw.Bars.Count=5520;
                        if(Mode=="rows10002")Raw.Bars.Count=10002;
                        if(Mode=="mutation_during_matrix")Raw.Bars.OnAdvance=()=>Raw.Bars.ChangedPrice=true;
                        if(Mode=="policy_during_matrix")Raw.Bars.OnAdvance=()=>Raw.LookupPolicy=NinjaTrader.Cbi.LookupPolicies.Provider;
                        if(Mode=="duplicate_in_matrix")Raw.Bars.OnAdvance=()=>Raw.Fire();
                        if(Mode=="terminate_in_matrix")Raw.Bars.OnAdvance=()=>Life.Terminate(Owner);
                    };
                    if(Mode=="request_dispose_error")Raw.OnDispose=()=> { throw new InvalidOperationException("PRIVATE_PROVIDER_SENTINEL"); };
                    return Wrapped;
                },(r,checkpoint)=> {
                    Plan=Context.Bind(Owner,r.Identity);
                    var factory=new SessionTimestampNativeCursorFactoryV1(Context.BoundBars(Owner),Plan,checkpoint,(phase,c)=>Context.Check(Owner,phase,c));
                    Report=new SessionTimestampExecutorV1().Execute(Plan,factory.Create,factory.Check);Context.Revalidate(Owner);return Report;
                },report=> {
                    if(Mode=="foreign_before_prepare")File.WriteAllText(Path.Combine(Capture,"foreign.txt"),"KEEP");
                    if(Mode=="foreign_plan")
                    {
                        var other=SessionTimestampPlanV1.Build(Plan.RawFirst,Plan.RawLast,Plan.ReturnedRows,Plan.SnapshotSha256,Plan.TemplateSha256,
                            NinjaTrader.Data.TradingHours.Next.TimeZoneInfo);
                        Writer.Prepare(Owner,other,report);return;
                    }
                    if(Mode=="foreign_owner_prepare")Reject(()=>Writer.Prepare(new object(),Plan,report));
                    Writer.Prepare(Owner,Plan,report);
                    if(Mode=="repeat_prepare")Writer.Prepare(Owner,Plan,report);
                    if(Mode=="mutation_after_prepare")Raw.Bars.ChangedPrice=true;
                    if(Mode=="environment_after_prepare")Gates=false;
                },phase=>Context.CheckLifecycle(Owner,phase));
        }
        internal void Complete()
        {
            Start();if(Raw==null || Mode=="inline" || Mode=="inline_then_throw" || Mode=="duplicate_inline" || Mode=="submit_error")return;
            if(Mode=="clone_writer")
            {
                var clone=Clone(Writer);clone.Dispose();Reject(()=>clone.PublishSeal(Owner));
                Check(Raw.Disposes==0,"CLONE_CLOSED_REQUEST");
            }
            if(Mode=="async") { var thread=new Thread(Raw.Fire);thread.Start();thread.Join(); }else Raw.Fire();
        }
    }
    static string Contents(string folder)
    {
        var files=Directory.GetFiles(folder,"*",SearchOption.AllDirectories);Array.Sort(files,StringComparer.Ordinal);var s=new StringBuilder();
        using(var h=SHA256.Create())foreach(var path in files)
            s.Append(path.Substring(folder.Length)).Append('|').Append(BitConverter.ToString(h.ComputeHash(File.ReadAllBytes(path))));
        return s.ToString();
    }
    static string EnvelopePath(Attempt a) { return Path.Combine(a.Capture,SessionTimestampContextEnvelopeV1.SealName); }
    static void CheckReady(Attempt a)
    {
        var state=a.Life.Inspect(a.Owner);
        Check(state.ReadyForSeal && a.Report.MatrixCompleted,"NOT_READY:"+state.StopGuard+":"+a.Context.FailureGuard);
        Check(a.Raw.Invokes==1 && a.Raw.Disposes==1,"REQUEST_CLOSE_NOT_ONCE");
        Check(a.Report.ConstructorAttempts==a.Raw.Bars.Creates && a.Report.CallAttempts==a.Raw.Bars.Calls &&
            a.Raw.Bars.Creates<=11 && a.Raw.Bars.Calls<=12,"NATIVE_DOUBLE_BUDGET");
    }
    static void Success(string folder,string mode)
    {
        Reset(mode);var a=new Attempt(folder,mode);a.Complete();CheckReady(a);
        if(mode=="foreign_owner_publish")Reject(()=>a.Writer.PublishSeal(new object()));
        int reads=a.Raw.Bars.TimeReads,calls=a.Raw.Bars.Calls;
        a.Writer.PublishSeal(a.Owner);Check(a.Writer.Sealed && File.Exists(EnvelopePath(a)),"ENVELOPE_MISSING");
        Check(reads==a.Raw.Bars.TimeReads && calls==a.Raw.Bars.Calls,"PUBLISH_READS_DISPOSED_SNAPSHOT");
        string before=Contents(a.Capture);
        a.Raw.Fire();a.Wrapped.Dispose();a.Writer.Dispose();
        Reject(()=>a.Writer.PublishSeal(a.Owner));
        Check(before==Contents(a.Capture) && a.Raw.Disposes==1,"LATE_ACTIVITY_CHANGED_FILES");
        Check(File.ReadAllText(Path.Combine(a.Capture,SessionTimestampContextEnvelopeV1.ContextName))==a.Context.CapturedContext(a.Owner),"CONTEXT_BYTES_NOT_EXACT");
        Check(Directory.GetFiles(a.Capture,"*",SearchOption.AllDirectories).Length==4,"UNEXPECTED_ENVELOPE_FILE_COUNT");
        foreach(var path in Directory.GetFiles(a.Capture,"*",SearchOption.AllDirectories))
            Check(!File.ReadAllText(path).Contains("PRIVATE_PROVIDER_SENTINEL"),"PRIVATE_TEXT_LEAK");
    }
    static void Failure(string folder,string mode)
    {
        Reset(mode);var a=new Attempt(folder,mode);
        if(mode=="foreign_before_open")File.WriteAllText(Path.Combine(a.Capture,"foreign.txt"),"KEEP");
        a.Complete();var state=a.Life.Inspect(a.Owner);
        Check(!state.ReadyForSeal && state.Status=="FAILED_CLOSED","FAILURE_NOT_BLOCKED");
        if(a.Writer!=null)Reject(()=>a.Writer.PublishSeal(a.Owner));
        Check(!File.Exists(EnvelopePath(a)),"FAILURE_HAS_ENVELOPE");
        Check(a.Raw==null || a.Raw.Disposes==1,"FAILED_REQUEST_LEAK");
        if(mode=="foreign_before_open")Check(File.ReadAllText(Path.Combine(a.Capture,"foreign.txt"))=="KEEP","OVERWROTE_FOREIGN_FILE");
    }
    static void Corruption(string folder,string mode)
    {
        Reset("normal");var a=new Attempt(folder,"normal");a.Complete();CheckReady(a);
        string ctx=Path.Combine(a.Capture,SessionTimestampContextEnvelopeV1.ContextName);
        string matrix=Path.Combine(a.Capture,"matrix",SessionTimestampEvidenceV1.DiagnosticName);
        string retained=null;
        if(mode=="context_bytes")File.AppendAllText(ctx," ");
        else if(mode=="matrix_bytes")File.AppendAllText(matrix," ");
        else if(mode=="context_missing")File.Move(ctx,Path.Combine(folder,"preserved-context.json"));
        else if(mode=="foreign_root") { retained=Path.Combine(a.Capture,"foreign.txt");File.WriteAllText(retained,"KEEP"); }
        else if(mode=="foreign_matrix") { retained=Path.Combine(a.Capture,"matrix","foreign.txt");File.WriteAllText(retained,"KEEP"); }
        else if(mode=="existing_temp") { retained=Path.Combine(a.Capture,"session-timestamp-context.done.tmp");File.WriteAllText(retained,"KEEP"); }
        else if(mode=="existing_envelope") { retained=EnvelopePath(a);File.WriteAllText(retained,"KEEP"); }
        else if(mode=="environment")a.Gates=false;
        else if(mode=="invalidation")a.Context.Invalidate(a.Owner);
        else if(mode=="context_length_state")typeof(SessionTimestampContextEnvelopeV1).GetField("contextBytes",BindingFlags.Instance|BindingFlags.NonPublic).SetValue(a.Writer,1);
        else if(mode=="inner_seal_only")
        {
            var writer=(SessionTimestampEvidenceV1)typeof(SessionTimestampContextEnvelopeV1).GetField("matrixWriter",BindingFlags.Instance|BindingFlags.NonPublic).GetValue(a.Writer);
            writer.PublishSeal(a.Owner);Check(writer.Sealed,"INNER_SEAL_SETUP");
        }
        else throw new Exception("UNKNOWN_CORRUPTION_CASE");
        Reject(()=>a.Writer.PublishSeal(a.Owner));Check(!a.Writer.Sealed,"CORRUPTION_SEALED");
        if(mode!="existing_envelope")Check(!File.Exists(EnvelopePath(a)),"INVALID_ENVELOPE_PUBLISHED");
        if(retained!=null)Check(File.ReadAllText(retained)=="KEEP","FOREIGN_FILE_MODIFIED");
        Check(a.Raw.Disposes==1,"CORRUPTION_DISPOSED_AGAIN");
    }
    static void RunCase(string root,string name)
    {
        string folder=Fresh(root,name);
        if(name.StartsWith("success_",StringComparison.Ordinal)) { Success(folder,name.Substring(8));return; }
        if(name.StartsWith("failure_",StringComparison.Ordinal)) { Failure(folder,name.Substring(8));return; }
        if(name.StartsWith("corrupt_",StringComparison.Ordinal)) { Corruption(folder,name.Substring(8));return; }
        if(name=="pending_early_seal")
        {
            Reset("normal");var a=new Attempt(folder,"normal");a.Start();
            Check(a.Raw.Bars.Calls==0 && a.Raw.Bars.TimeReads==0,"PENDING_EXECUTED");
            Reject(()=>a.Writer.PublishSeal(a.Owner));a.Life.Terminate(a.Owner);
            Check(!File.Exists(EnvelopePath(a)) && a.Raw.Disposes==1,"PENDING_SEALED_OR_LEAKED");return;
        }
        throw new Exception("UNKNOWN_CASE");
    }
    internal static readonly string[] SuccessModes={
        "normal","inline","async","all_false","false","constructor_error","advance_error","begin_error","end_error","bad_order","bad_kind",
        "r0_false","r0_constructor_error","r0_advance_error","r0_begin_error","r0_end_error","r0_bad_order","r0_bad_kind",
        "mixed","duplicate","decreasing","misaligned","rows4503","rows5520","rows10002","irrelevant_exceptions",
        "clone_writer","foreign_owner_prepare","foreign_owner_publish","native_origin_claim" };
    internal static readonly string[] FailureModes={
        "inline_then_throw","duplicate_inline","callback_error","wrong_callback","submit_error","mutation_during_matrix","policy_during_matrix",
        "duplicate_in_matrix","terminate_in_matrix","foreign_before_open","foreign_before_prepare","foreign_plan","repeat_prepare",
        "mutation_after_prepare","environment_after_prepare","request_dispose_error" };
    internal static readonly string[] CorruptionModes={
        "context_bytes","matrix_bytes","context_missing","foreign_root","foreign_matrix","existing_temp","existing_envelope",
        "environment","invalidation","context_length_state","inner_seal_only" };
    internal static List<string> Inventory()
    {
        var names=new List<string>();foreach(var m in SuccessModes)names.Add("success_"+m);
        foreach(var m in FailureModes)names.Add("failure_"+m);foreach(var m in CorruptionModes)names.Add("corrupt_"+m);
        names.Add("pending_early_seal");return names;
    }
    public static int Main(string[] args)
    {
        if(args.Length==3 && args[0]=="--emit")
        {
            Check(Array.IndexOf(SuccessModes,args[2])>=0,"UNKNOWN_EMIT_MODE");Success(args[1],args[2]);
            Console.WriteLine("{\"classification\":\"SYNTHETIC_CONTEXT_ENVELOPE_ONLY\",\"sealed\":true}");return 0;
        }
        if(args.Length<2)return 2;int passed=0,failed=0;var results=new List<object>();
        foreach(string name in Inventory())
        {
            if(args[0]!="--all" && !(args[0]=="--case" && args.Length==3 && name==args[2]))continue;
            try { RunCase(args[1],name);results.Add(new { name=name,status="PASS",detail="NONE" });passed++; }
            catch(Exception e) { results.Add(new { name=name,status="FAIL",detail=e.GetType().Name+":"+e.Message });failed++; }
        }
        Console.WriteLine(new JavaScriptSerializer().Serialize(new { classification="SYNTHETIC_CONTEXT_ENVELOPE_ONLY",total=passed+failed,passed=passed,failed=failed,
            real_native_api_calls=0,loaded_ninjatrader_assemblies=Array.FindAll(AppDomain.CurrentDomain.GetAssemblies(),a=>a.GetName().Name.StartsWith("NinjaTrader",StringComparison.Ordinal)).Length,results=results }));
        return failed==0 && passed>0?0:1;
    }
}
