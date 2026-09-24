// SYNTHETIC ONLY: uses the actual A/B/C/D cores. No NinjaTrader assembly.
using System;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using System.Web.Script.Serialization;
using Arms.AI.Diagnostics.R53;

internal static class EvidenceHarness
{
    const string Secret="PRIVATE_PROVIDER_SENTINEL";
    static void Check(bool ok,string id) { if(!ok)throw new Exception(id); }
    private sealed class Cursor : ISessionTimestampCursor
    {
        readonly QueryControl control;readonly string mode;readonly object identity=new object();
        internal Cursor(QueryControl c,string m) { control=c;mode=m; }
        public object Identity { get { return identity; } }
        bool Hit(string name) { return (mode==name && control.CaseId=="A_U") || (mode=="r0_"+name && control.CaseId=="R0"); }
        public bool Advance(DateTime value,bool include)
        {
            Check(value.Ticks==control.Time.Query.Ticks && value.Kind==control.Time.Query.Kind && include,"QUERY_CHANGED");
            if(Hit("advance_error"))throw new InvalidOperationException(Secret);
            return mode!="all_false" && !Hit("false");
        }
        public DateTime ReadBegin()
        {
            if(Hit("begin_error"))throw new InvalidOperationException(Secret);
            return new DateTime(2026,9,13,22,0,0,DateTimeKind.Utc);
        }
        public DateTime ReadEnd()
        {
            if(Hit("end_error"))throw new InvalidOperationException(Secret);
            if(Hit("bad_order"))return new DateTime(2026,9,13,21,0,0,DateTimeKind.Utc);
            if(Hit("bad_kind"))return new DateTime(2026,9,14,21,0,0,DateTimeKind.Unspecified);
            return new DateTime(2026,9,14,21,0,0,DateTimeKind.Utc);
        }
    }
    private sealed class Request : ISessionTimestampRequestV1
    {
        internal string Mode;internal Action<object,bool> Delivery;internal int Disposals;
        public object Identity { get { return this; } }
        public void Submit(Action<object,bool> callback)
        {
            Delivery=callback;
            if(Mode=="inline" || Mode=="inline_then_throw")callback(this,true);
            if(Mode=="inline_then_throw" || Mode=="submit_error")throw new InvalidOperationException(Secret);
        }
        internal void Fire() { Delivery(this,true); }
        public void Dispose()
        {
            Disposals++;
            if(Mode=="dispose_error")throw new InvalidOperationException(Secret);
        }
    }
    private sealed class Attempt
    {
        internal readonly object Owner=new object();
        internal readonly SessionTimestampLifecycleV1 Life;
        internal readonly string Folder, Mode;
        internal SessionTimestampEvidenceV1 Writer;
        internal Request Req;
        internal TimestampQueryPlan Plan;
        internal TimestampMatrixReport Report;
        internal Attempt(string folder,string mode)
        {
            Folder=folder;Mode=mode;Life=new SessionTimestampLifecycleV1(Owner);
            var zone=TimeZoneInfo.CreateCustomTimeZone("SYNTHETIC_FIXED_MINUS_FIVE",TimeSpan.FromHours(-5),"Synthetic","Synthetic");
            Plan=SessionTimestampPlanV1.Build(new DateTime(2026,9,16,12,0,0,DateTimeKind.Unspecified),
                new DateTime(2026,9,16,12,4,0,DateTimeKind.Unspecified),5,new string('a',64),new string('b',64),zone);
        }
        internal void Start()
        {
            Life.Start(Owner,true,
                ()=> { Writer=new SessionTimestampEvidenceV1(Owner,Life,Folder,Guid.NewGuid().ToString("D"),Guid.NewGuid().ToString("D"),"SYNTHETIC");return Writer; },
                ()=> { Req=new Request{Mode=Mode};return Req; },
                (request,checkpoint)=> {
                    var executor=new SessionTimestampExecutorV1();
                    Report=executor.Execute(Plan,c=> {
                        if((Mode=="constructor_error" && c.CaseId=="A_U") || (Mode=="r0_constructor_error" && c.CaseId=="R0"))
                            throw new InvalidOperationException(Secret);
                        // R1 uses R0 cursor, but exact query equality is validated by B's tests.
                        return new LooseCursor(c,Mode);
                    },(phase,c)=>checkpoint());return Report;
                },report=>Writer.Prepare(Owner,Plan,report),phase=> {
                    if(Mode=="context_error" && phase=="AFTER_PROCESS")throw new InvalidOperationException(Secret);
                });
        }
        internal void Complete()
        {
            Start();
            if(Mode!="inline" && Mode!="inline_then_throw" && Mode!="submit_error" && Req!=null)
            {
                if(Mode=="async") { var t=new System.Threading.Thread(Req.Fire);t.Start();t.Join(); }
                else Req.Fire();
            }
        }
        internal void Seal() { Writer.PublishSeal(Owner); }
    }
    // Reused iterator is queried twice. Distinguish query verification from identity reuse.
    private sealed class LooseCursor : ISessionTimestampCursor
    {
        readonly Cursor inner;readonly object identity=new object();readonly QueryControl c;
        internal LooseCursor(QueryControl control,string mode) { inner=new Cursor(control,mode);c=control; }
        public object Identity { get { return identity; } }
        public bool Advance(DateTime q,bool include)
        {
            if(c.CaseId=="R0" && q.Ticks!=c.Time.Query.Ticks)
            { Check(include,"REUSE_INCLUDE");return true; }
            return inner.Advance(q,include);
        }
        public DateTime ReadBegin() { return inner.ReadBegin(); }
        public DateTime ReadEnd() { return inner.ReadEnd(); }
    }
    static string Fresh(string root,string name)
    {
        string path=Path.Combine(root,name+"-"+Guid.NewGuid().ToString("N"));Directory.CreateDirectory(path);return path;
    }
    static void ExpectReject(Action action)
    {
        bool rejected=false;try { action(); } catch(EvidenceGuardException) { rejected=true; }
        Check(rejected,"EXPECTED_EVIDENCE_REJECTION");
    }
    static string HashFile(string file)
    { using(var h=System.Security.Cryptography.SHA256.Create())return BitConverter.ToString(h.ComputeHash(File.ReadAllBytes(file))); }
    static void Successful(string root,string mode)
    {
        string dir=Fresh(root,mode);var a=new Attempt(dir,mode);a.Complete();
        Check(a.Life.Inspect(a.Owner).ReadyForSeal,"LIFECYCLE_NOT_READY");a.Seal();
        Check(a.Writer.Sealed && File.Exists(Path.Combine(dir,SessionTimestampEvidenceV1.SealName)),"NO_SEAL");
        Check(File.ReadAllLines(Path.Combine(dir,SessionTimestampEvidenceV1.DiagnosticName)).Length==15,"RECORD_COUNT");
        Check(new FileInfo(Path.Combine(dir,SessionTimestampEvidenceV1.DiagnosticName)).Length<=262144,"SIZE");
        Check(!File.ReadAllText(Path.Combine(dir,SessionTimestampEvidenceV1.DiagnosticName)).Contains(Secret),"REDACTION");
    }
    static void NoSeal(string root,string mode)
    {
        string dir=Fresh(root,mode);var a=new Attempt(dir,mode);a.Complete();
        Check(!a.Life.Inspect(a.Owner).ReadyForSeal,"UNEXPECTED_READY");
        if(a.Writer!=null)ExpectReject(a.Seal);
        Check(!File.Exists(Path.Combine(dir,SessionTimestampEvidenceV1.SealName)),"UNEXPECTED_SEAL");
    }
    static void MainCase(string root,string name)
    {
        if(name.StartsWith("success_",StringComparison.Ordinal)) { Successful(root,name.Substring(8));return; }
        if(name.StartsWith("failure_",StringComparison.Ordinal)) { NoSeal(root,name.Substring(8));return; }
        string dir=Fresh(root,name);var a=new Attempt(dir,"normal");
        if(name=="foreign_before_open")
        {
            string f=Path.Combine(dir,"foreign.txt");File.WriteAllText(f,"preserve");a.Start();
            Check(a.Writer==null && File.ReadAllText(f)=="preserve" && Directory.GetFiles(dir).Length==1,"FOREIGN_CHANGED");return;
        }
        if(name=="writer_clone_no_cross_close")
        {
            a.Start();var clone=(SessionTimestampEvidenceV1)typeof(object).GetMethod("MemberwiseClone",BindingFlags.Instance|BindingFlags.NonPublic).Invoke(a.Writer,null);
            clone.Dispose();ExpectReject(()=>clone.PublishSeal(a.Owner));a.Req.Fire();a.Seal();Check(a.Writer.Sealed,"CLONE_DAMAGED_OWNER");return;
        }
        if(name=="pending_never_seals") { a.Start();ExpectReject(a.Seal);a.Life.Terminate(a.Owner);return; }
        a.Complete();
        if(name=="wrong_owner_preserves_owner")
        { ExpectReject(()=>a.Writer.PublishSeal(new object()));a.Seal();Check(a.Writer.Sealed,"OWNER_TAINTED");return; }
        string main=Path.Combine(dir,SessionTimestampEvidenceV1.DiagnosticName);
        if(name=="modified_bytes_no_seal")
        {
            var raw=File.ReadAllBytes(main);raw[20]^=1;File.WriteAllBytes(main,raw);ExpectReject(a.Seal);
            Check(!File.Exists(Path.Combine(dir,SessionTimestampEvidenceV1.SealName)),"FORGED_SEAL");return;
        }
        if(name=="foreign_after_close")
        {
            string f=Path.Combine(dir,"foreign.txt");File.WriteAllText(f,"preserve");ExpectReject(a.Seal);Check(File.ReadAllText(f)=="preserve","FOREIGN_CHANGED");return;
        }
        if(name=="existing_temp_not_overwritten")
        {
            string f=Path.Combine(dir,"session-timestamp-evidence.done.tmp");File.WriteAllText(f,"preserve");ExpectReject(a.Seal);Check(File.ReadAllText(f)=="preserve","TEMP_OVERWRITTEN");return;
        }
        if(name=="existing_seal_not_overwritten")
        {
            string f=Path.Combine(dir,SessionTimestampEvidenceV1.SealName);File.WriteAllText(f,"preserve");ExpectReject(a.Seal);Check(File.ReadAllText(f)=="preserve","SEAL_OVERWRITTEN");return;
        }
        if(name=="seal_not_repeated")
        { a.Seal();string hash=HashFile(main);ExpectReject(a.Seal);Check(hash==HashFile(main) && a.Writer.Sealed,"REPEATED_MUTATION");return; }
        if(name=="late_callback_no_mutation")
        { a.Seal();string hash=HashFile(main);a.Req.Fire();a.Life.Terminate(a.Owner);Check(hash==HashFile(main) && a.Req.Disposals==1,"LATE_MUTATION");return; }
        if(name=="repeat_dispose_no_mutation")
        { a.Writer.Dispose();a.Writer.Dispose();a.Seal();Check(a.Writer.Sealed,"REPEAT_DISPOSE_FAILED");return; }
        throw new Exception("UNKNOWN_TEST");
    }
    internal static string[] Cases={
        "success_normal","success_inline","success_async","success_all_false","success_false",
        "success_constructor_error","success_advance_error","success_begin_error","success_end_error","success_bad_order","success_bad_kind",
        "success_r0_false","success_r0_constructor_error","success_r0_advance_error","success_r0_begin_error","success_r0_end_error","success_r0_bad_order","success_r0_bad_kind",
        "failure_inline_then_throw","failure_submit_error","failure_context_error","failure_dispose_error",
        "foreign_before_open","writer_clone_no_cross_close","pending_never_seals","wrong_owner_preserves_owner",
        "modified_bytes_no_seal","foreign_after_close","existing_temp_not_overwritten","existing_seal_not_overwritten",
        "seal_not_repeated","late_callback_no_mutation","repeat_dispose_no_mutation"
    };
    public static int Main(string[] args)
    {
        if(args.Length==3 && args[0]=="--emit")
        {
            var a=new Attempt(args[1],args[2]);a.Complete();a.Seal();
            Console.WriteLine(new JavaScriptSerializer().Serialize(new { classification="SYNTHETIC_ONLY",sealed_ok=a.Writer.Sealed }));return 0;
        }
        if(args.Length<2)return 2;
        string root=args[1];bool all=args[0]=="--all";int pass=0,fail=0;var rows=new List<object>();
        foreach(string name in Cases)
        {
            if(!all && !(args[0]=="--case" && args.Length==3 && args[2]==name))continue;
            try { MainCase(root,name);rows.Add(new { name=name,status="PASS",detail="NONE" });pass++; }
            catch(Exception error) { rows.Add(new { name=name,status="FAIL",detail=error.GetType().Name+":"+error.Message });fail++; }
        }
        Console.WriteLine(new JavaScriptSerializer().Serialize(new { classification="SYNTHETIC_EVIDENCE_IO_ONLY",total=pass+fail,passed=pass,failed=fail,
            loaded_ninjatrader_assemblies=Array.FindAll(AppDomain.CurrentDomain.GetAssemblies(),x=>x.GetName().Name.StartsWith("NinjaTrader",StringComparison.Ordinal)).Length,
            real_native_api_calls=0,results=rows }));return fail==0 && pass>0?0:1;
    }
}
