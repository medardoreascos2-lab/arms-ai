// EXPLICIT SDK DOUBLES. This executable must NOT reference NinjaTrader DLLs.
// The exact E bridge + A/B/C/D execute here, but native behavior is NOT attested.
using System;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using System.Threading;
using System.Web.Script.Serialization;
using Arms.AI.Diagnostics.R53;
[assembly: AssemblyVersion("8.1.8.2")]
namespace NinjaTrader.Cbi { public enum ErrorCode { NoError, Failed } }
namespace NinjaTrader.Data
{
    public sealed class Bars
    {
        public string Mode="normal";
        public int Creates, Calls, Begins, Ends;
        public Action OnCreate, OnAdvance, OnBegin, OnEnd;
        public readonly List<SessionIterator> Instances=new List<SessionIterator>();
        public readonly List<DateTime> Queries=new List<DateTime>();
        public readonly List<int> QuerySlots=new List<int>();
        public readonly List<bool> Includes=new List<bool>();
    }
    public sealed class SessionIterator
    {
        readonly Bars bars;readonly int number;bool returned;
        public SessionIterator(Bars value)
        {
            if(value==null)throw new Exception("BARS_NULL");
            bars=value;number=++bars.Creates;bars.Instances.Add(this);
            if(bars.OnCreate!=null)bars.OnCreate();
            if(Hit("constructor_error"))throw new InvalidOperationException(BridgeHarness.Secret);
        }
        bool Hit(string name)
        { return bars.Mode==name && number==1 || bars.Mode=="r0_"+name && number==10; }
        public bool GetNextSession(DateTime query,bool include)
        {
            bars.Calls++;bars.Queries.Add(query);bars.Includes.Add(include);bars.QuerySlots.Add(number);
            returned=false;if(bars.OnAdvance!=null)bars.OnAdvance();
            if(Hit("advance_error"))throw new InvalidOperationException(BridgeHarness.Secret);
            returned=bars.Mode!="all_false" && !Hit("false");return returned;
        }
        public DateTime ActualSessionBegin
        {
            get
            {
                bars.Begins++;if(!returned)throw new Exception("NATIVE_BEGIN_READ_AFTER_FALSE");
                if(bars.OnBegin!=null)bars.OnBegin();
                if(Hit("begin_error"))throw new InvalidOperationException(BridgeHarness.Secret);
                return new DateTime(2026,9,13,22,0,0,DateTimeKind.Utc);
            }
        }
        public DateTime ActualSessionEnd
        {
            get
            {
                bars.Ends++;if(!returned)throw new Exception("NATIVE_END_READ_AFTER_FALSE");
                if(bars.OnEnd!=null)bars.OnEnd();
                if(Hit("end_error"))throw new InvalidOperationException(BridgeHarness.Secret);
                if(Hit("bad_order"))return new DateTime(2026,9,13,21,0,0,DateTimeKind.Utc);
                return new DateTime(2026,9,14,21,0,0,Hit("bad_kind")?DateTimeKind.Unspecified:DateTimeKind.Utc);
            }
        }
    }
    public sealed class BarsRequest : IDisposable
    {
        public string Mode="normal";
        public Bars Bars=new Bars();
        public int Invokes, Disposes;
        public Action OnSubmit,OnDispose;
        private Action<BarsRequest,NinjaTrader.Cbi.ErrorCode,string> callback;
        public void Request(Action<BarsRequest,NinjaTrader.Cbi.ErrorCode,string> value)
        {
            Invokes++;callback=value;
            if(OnSubmit!=null)OnSubmit();
            if(Mode=="inline" || Mode=="inline_then_throw" || Mode=="duplicate_inline")Fire();
            if(Mode=="duplicate_inline")Fire();
            if(Mode=="submit_error" || Mode=="inline_then_throw")throw new InvalidOperationException(BridgeHarness.Secret);
        }
        public void Fire()
        {
            if(callback!=null)callback(Mode=="wrong_callback"?new BarsRequest():Mode=="null_callback"?null:this,
                Mode=="callback_error"?NinjaTrader.Cbi.ErrorCode.Failed:NinjaTrader.Cbi.ErrorCode.NoError,BridgeHarness.Secret);
        }
        public void Dispose()
        {
            Disposes++;if(OnDispose!=null)OnDispose();
            if(Mode=="dispose_error")throw new InvalidOperationException(BridgeHarness.Secret);
        }
    }
}
internal static class BridgeHarness
{
    internal const string Secret="PRIVATE_PROVIDER_SENTINEL";
    static void Check(bool ok,string id) { if(!ok)throw new Exception(id); }
    static void Reject(Action action)
    {
        bool rejected=false;try { action(); } catch(NativeBridgeGuardException) { rejected=true; }
        Check(rejected,"EXPECTED_BRIDGE_REJECTION");
    }
    static T Clone<T>(T value)
    { return (T)typeof(object).GetMethod("MemberwiseClone",BindingFlags.Instance|BindingFlags.NonPublic).Invoke(value,null); }
    static TimestampQueryPlan Plan()
    {
        var zone=TimeZoneInfo.CreateCustomTimeZone("SYNTHETIC_FIXED_MINUS_FIVE",TimeSpan.FromHours(-5),"Synthetic","Synthetic");
        return SessionTimestampPlanV1.Build(new DateTime(2026,9,16,12,0,0,DateTimeKind.Unspecified),
            new DateTime(2026,9,16,12,4,0,DateTimeKind.Unspecified),5,new string('a',64),new string('b',64),zone);
    }
    static string Fresh(string root,string name)
    { string path=Path.Combine(root,name+"-"+Guid.NewGuid().ToString("N"));Directory.CreateDirectory(path);return path; }
    private sealed class Attempt
    {
        internal readonly object Owner=new object();
        internal readonly SessionTimestampLifecycleV1 Life;
        internal readonly NinjaTrader.Data.BarsRequest Raw;
        internal readonly TimestampQueryPlan QueryPlan=Plan();
        internal readonly string Folder,Mode;
        internal SessionTimestampNativeRequestV1 Request;
        internal SessionTimestampNativeCursorFactoryV1 Factory;
        internal SessionTimestampEvidenceV1 Writer;
        internal TimestampMatrixReport Report;
        internal bool SubmitExited;
        internal Attempt(string folder,string mode)
        {
            Folder=folder;Mode=mode;Life=new SessionTimestampLifecycleV1(Owner);
            Raw=new NinjaTrader.Data.BarsRequest { Mode=mode };
            Raw.Bars.Mode=mode;
            if(mode=="terminate_in_submit")Raw.OnSubmit=()=>Life.Terminate(Owner);
            if(mode=="terminate_in_matrix")Raw.Bars.OnAdvance=()=>Life.Terminate(Owner);
            if(mode=="duplicate_in_matrix")Raw.Bars.OnAdvance=()=>Raw.Fire();
            if(mode=="dispose_callback")Raw.OnDispose=()=>Raw.Fire();
        }
        internal void Start()
        {
            Life.Start(Owner,true,
                ()=> { Writer=new SessionTimestampEvidenceV1(Owner,Life,Folder,Guid.NewGuid().ToString("D"),Guid.NewGuid().ToString("D"),"SYNTHETIC");return Writer; },
                ()=> { Request=new SessionTimestampNativeRequestV1(Owner,Raw,()=>{});return Request; },
                (request,checkpoint)=> {
                    Check(Object.ReferenceEquals(request.Identity,Raw),"NATIVE_REQUEST_IDENTITY_LOST");
                    Factory=new SessionTimestampNativeCursorFactoryV1(Raw.Bars,QueryPlan,checkpoint,(phase,control)=> {
                        if(Mode=="context_error" && phase=="SDK_BEFORE_ADVANCE")throw new InvalidOperationException(Secret);
                    });
                    Report=new SessionTimestampExecutorV1().Execute(QueryPlan,Factory.Create,Factory.Check);return Report;
                },report=> {
                    Check(Raw.Disposes==0,"EARLY_NATIVE_DISPOSE");Writer.Prepare(Owner,QueryPlan,report);
                },phase=>{});
            SubmitExited=true;
        }
        internal void Complete()
        {
            Start();
            if(Mode!="inline" && Mode!="inline_then_throw" && Mode!="duplicate_inline" && Mode!="submit_error" && Mode!="pending")
            {
                if(Mode=="async") { var t=new Thread(Raw.Fire);t.Start();t.Join(); }
                else Raw.Fire();
            }
        }
        internal void Seal() { Writer.PublishSeal(Owner); }
    }
    static void Success(string dir,string mode)
    {
        var a=new Attempt(dir,mode);a.Complete();var s=a.Life.Inspect(a.Owner);
        Check(s.ReadyForSeal && a.Report.MatrixCompleted && a.Raw.Invokes==1 && a.Raw.Disposes==1,"NOT_COMPLETE");
        Check(a.Request.NativeSubmitAttempts==1 && a.Request.NativeDisposeAttempts==1,"REQUEST_COUNTER_MISMATCH");
        Check(a.Raw.Bars.Creates==a.Report.ConstructorAttempts && a.Raw.Bars.Calls==a.Report.CallAttempts &&
            a.Raw.Bars.Begins==a.Report.BeginReadAttempts && a.Raw.Bars.Ends==a.Report.EndReadAttempts,"COUNTERS_NOT_MEASURED");
        Check(a.Factory.ConstructorAttempts==a.Raw.Bars.Creates && a.Factory.CallAttempts==a.Raw.Bars.Calls &&
            a.Factory.BeginReadAttempts==a.Raw.Bars.Begins && a.Factory.EndReadAttempts==a.Raw.Bars.Ends,"BRIDGE_COUNTER_MISMATCH");
        Check(a.Raw.Bars.Creates<=11 && a.Raw.Bars.Calls<=12,"BUDGET_EXCEEDED");
        foreach(bool include in a.Raw.Bars.Includes)Check(include,"INCLUSION_CHANGED");
        int index=0;
        foreach(var item in a.Report.Observations)
        {
            if(item.Outcome=="SKIPPED" || item.Outcome=="CONSTRUCTOR_EXCEPTION")continue;
            DateTime actual=a.Raw.Bars.Queries[index++];
            Check(actual.Ticks==item.Control.Time.Query.Ticks && actual.Kind==item.Control.Time.Query.Kind,"QUERY_CHANGED");
        }
        Check(index==a.Raw.Bars.Queries.Count,"QUERY_COUNT_INVALID");
        a.Seal();Check(a.Writer.Sealed,"NO_SEAL");
        Check(!File.ReadAllText(Path.Combine(dir,SessionTimestampEvidenceV1.DiagnosticName)).Contains(Secret),"PROVIDER_TEXT_LEAK");
        a.Raw.Fire();a.Request.Dispose();Check(a.Raw.Disposes==1,"SECOND_DISPOSE");
    }
    static void Failure(string dir,string mode)
    {
        var a=new Attempt(dir,mode);a.Complete();var s=a.Life.Inspect(a.Owner);
        Check(!s.ReadyForSeal && s.Status=="FAILED_CLOSED","FAILURE_SEALED");
        bool refused=false;try { a.Seal(); } catch(EvidenceGuardException) { refused=true; }
        Check(refused && !File.Exists(Path.Combine(dir,SessionTimestampEvidenceV1.SealName)),"SEAL_NOT_REJECTED");
        Check(a.Raw.Invokes<=1 && a.Raw.Disposes==1,"FAILED_REQUEST_CLEANUP_INVALID");
        Check(a.Raw.Bars.Creates<=11 && a.Raw.Bars.Calls<=12,"FAILURE_BUDGET");
    }
    static void MainCase(string root,string name)
    {
        if(name.StartsWith("success_",StringComparison.Ordinal)) { Success(Fresh(root,name),name.Substring(8));return; }
        if(name.StartsWith("failure_",StringComparison.Ordinal)) { Failure(Fresh(root,name),name.Substring(8));return; }
        var owner=new object();var raw=new NinjaTrader.Data.BarsRequest();var p=Plan();
        var req=new SessionTimestampNativeRequestV1(owner,raw,()=>{});
        var bars=new NinjaTrader.Data.Bars();
        var factory=new SessionTimestampNativeCursorFactoryV1(bars,p,()=>{},(phase,c)=>{});
        if(name=="request_identity") { Check(Object.ReferenceEquals(req.Identity,raw) && req.IsOwner(owner) && !req.IsOwner(new object()),"IDENTITY");req.Dispose();return; }
        if(name=="request_sender_and_error")
        {
            raw.Mode="callback_error";object seen=null;bool status=true;
            req.Submit((sender,ok)=>{ seen=sender;status=ok; });raw.Fire();
            Check(Object.ReferenceEquals(seen,raw) && !status,"CALLBACK_MAPPING");req.Dispose();return;
        }
        if(name=="request_repeated_submit") { req.Submit((o,b)=>{});Reject(()=>req.Submit((o,b)=>{}));Check(raw.Invokes==1,"RESUBMIT");req.Dispose();return; }
        if(name=="request_after_dispose") { req.Dispose();Reject(()=>req.Submit((o,b)=>{}));Check(raw.Invokes==0 && raw.Disposes==1,"AFTER_DISPOSE");return; }
        if(name=="request_null_callback") { Reject(()=>req.Submit(null));Check(raw.Invokes==0,"NULL_CALLBACK");req.Dispose();return; }
        if(name=="request_context_rejected")
        {
            req=new SessionTimestampNativeRequestV1(owner,raw,()=>{throw new ArgumentException(Secret);});
            bool rejected=false;try { req.Submit((o,b)=>{}); } catch(ArgumentException) { rejected=true; }
            Check(rejected && raw.Invokes==0,"CONTEXT_BYPASSED");req.Dispose();return;
        }
        if(name=="request_clone_preserves_owner")
        {
            var clone=Clone(req);clone.Dispose();Reject(()=>clone.Submit((o,b)=>{}));Reject(()=>{var x=clone.Identity;});
            Check(!clone.IsOwner(owner) && raw.Disposes==0,"CLONE_CLOSED_OWNER");req.Submit((o,b)=>{});req.Dispose();Check(raw.Invokes==1 && raw.Disposes==1,"OWNER_BROKEN");return;
        }
        if(name=="request_late_callback_ignored")
        { int received=0;req.Submit((o,b)=>received++);req.Dispose();raw.Fire();Check(received==0,"LATE_CALLBACK_FORWARDED");return; }
        if(name=="request_dispose_throws_once")
        {
            raw.Mode="dispose_error";bool failed=false;try { req.Dispose(); } catch(InvalidOperationException) { failed=true; }
            req.Dispose();Check(failed && raw.Disposes==1 && req.NativeDisposeAttempts==1,"DISPOSE_RETRIED");return;
        }
        if(name=="request_dispose_during_submit_rejected")
        {
            raw.OnSubmit=()=>Reject(req.Dispose);req.Submit((o,b)=>{});
            Check(raw.Disposes==0,"INFLIGHT_DISPOSE");req.Dispose();Check(raw.Disposes==1,"AFTER_SUBMIT_DISPOSE");return;
        }
        if(name=="factory_clone_preserves_owner")
        {
            var clone=Clone(factory);clone.Invalidate();Reject(()=>clone.Create(p.Cases[0]));
            var c=factory.Create(p.Cases[0]);Check(bars.Creates==1 && c.Identity!=null,"OWNER_FACTORY_BROKEN");return;
        }
        if(name=="cursor_clone_preserves_owner")
        {
            var c=factory.Create(p.Cases[0]);var clone=Clone(c);Reject(()=>clone.Advance(p.Cases[0].Time.Query,true));
            Check(bars.Calls==0 && c.Advance(p.Cases[0].Time.Query,true),"CLONE_QUERY");return;
        }
        if(name=="native_identity_preserved")
        { var c=factory.Create(p.Cases[0]);Check(Object.ReferenceEquals(c.Identity,bars.Instances[0]),"FABRICATED_IDENTITY");return; }
        if(name=="factory_duplicate_slot_rejected")
        { factory.Create(p.Cases[0]);Reject(()=>factory.Create(p.Cases[0]));Check(bars.Creates==1,"DUPLICATE_SLOT");return; }
        if(name=="factory_reuse_construction_rejected")
        { Reject(()=>factory.Create(p.Cases[10]));Check(bars.Creates==0,"R1_CREATED");return; }
        if(name=="factory_foreign_control_rejected")
        { Reject(()=>factory.Create(Plan().Cases[0]));Check(bars.Creates==0,"FOREIGN_PLAN");return; }
        if(name=="factory_invalidation")
        { var c=factory.Create(p.Cases[0]);factory.Invalidate();Reject(()=>c.Advance(p.Cases[0].Time.Query,true));Check(bars.Calls==0,"INVALIDATED_USED");return; }
        if(name=="native_query_kind_changed")
        { var c=factory.Create(p.Cases[0]);Reject(()=>c.Advance(DateTime.SpecifyKind(p.Cases[0].Time.Query,DateTimeKind.Utc),true));Check(bars.Calls==0,"KIND_CHANGED");return; }
        if(name=="native_query_ticks_changed")
        { var c=factory.Create(p.Cases[0]);Reject(()=>c.Advance(p.Cases[0].Time.Query.AddTicks(1),true));Check(bars.Calls==0,"TICKS_CHANGED");return; }
        if(name=="native_query_inclusion_changed")
        { var c=factory.Create(p.Cases[0]);Reject(()=>c.Advance(p.Cases[0].Time.Query,false));Check(bars.Calls==0,"INCLUSION_CHANGED");return; }
        if(name=="bounds_before_advance_rejected")
        { var c=factory.Create(p.Cases[0]);Reject(()=>c.ReadBegin());Check(bars.Begins==0,"EARLY_BEGIN");return; }
        if(name=="bounds_after_false_rejected")
        { bars.Mode="false";var c=factory.Create(p.Cases[0]);Check(!c.Advance(p.Cases[0].Time.Query,true),"FALSE_NOT_PASSED");Reject(()=>c.ReadBegin());Check(bars.Begins==0 && bars.Ends==0,"FALSE_BOUNDS");return; }
        if(name=="end_before_begin_rejected")
        { var c=factory.Create(p.Cases[0]);c.Advance(p.Cases[0].Time.Query,true);Reject(()=>c.ReadEnd());Check(bars.Ends==0,"EARLY_END");return; }
        if(name=="duplicate_begin_rejected")
        { var c=factory.Create(p.Cases[0]);c.Advance(p.Cases[0].Time.Query,true);c.ReadBegin();Reject(()=>c.ReadBegin());Check(bars.Begins==1,"BEGIN_RETRIED");return; }
        if(name=="ordinary_cursor_reuse_rejected")
        { var c=factory.Create(p.Cases[0]);c.Advance(p.Cases[0].Time.Query,true);c.ReadBegin();c.ReadEnd();Reject(()=>c.Advance(p.Cases[0].Time.Query,true));Check(bars.Calls==1,"UNPLANNED_REUSE");return; }
        if(name=="request_and_factory_dependencies")
        {
            Reject(()=>new SessionTimestampNativeRequestV1(null,raw,()=>{}));
            Reject(()=>new SessionTimestampNativeRequestV1(owner,null,()=>{}));
            Reject(()=>new SessionTimestampNativeRequestV1(owner,raw,null));
            Reject(()=>new SessionTimestampNativeCursorFactoryV1(null,p,()=>{},(s,c)=>{}));
            Reject(()=>new SessionTimestampNativeCursorFactoryV1(bars,null,()=>{},(s,c)=>{}));
            Reject(()=>new SessionTimestampNativeCursorFactoryV1(bars,p,null,(s,c)=>{}));
            Reject(()=>new SessionTimestampNativeCursorFactoryV1(bars,p,()=>{},null));return;
        }
        if(name=="checkpoint_blocks_constructor")
        {
            factory=new SessionTimestampNativeCursorFactoryV1(bars,p,()=>{throw new InvalidOperationException(Secret);},(s,c)=>{});
            Reject(()=>factory.Create(p.Cases[0]));Check(bars.Creates==0,"CHECKPOINT_BYPASSED");return;
        }
        if(name=="reentrant_native_call_stops_matrix")
        {
            ISessionTimestampCursor c=null;c=factory.Create(p.Cases[0]);bars.OnAdvance=()=>Reject(()=>c.Advance(p.Cases[0].Time.Query,true));
            c.Advance(p.Cases[0].Time.Query,true);Reject(()=>factory.Check("AFTER_CASE",p.Cases[0]));Check(bars.Calls==1,"REENTRANT_EXTRA_CALL");return;
        }
        if(name=="pending_termination")
        {
            string dir=Fresh(root,name);var a=new Attempt(dir,"pending");a.Start();
            Check(!a.Life.Inspect(a.Owner).ReadyForSeal,"PENDING_SEALED");a.Life.Terminate(a.Owner);
            Check(a.Raw.Disposes==1 && a.Raw.Bars.Calls==0,"PENDING_CLEANUP");return;
        }
        throw new Exception("UNKNOWN_TEST");
    }
    internal static string[] Cases={
        "success_normal","success_inline","success_async","success_all_false","success_false",
        "success_constructor_error","success_advance_error","success_begin_error","success_end_error","success_bad_order","success_bad_kind",
        "success_r0_false","success_r0_constructor_error","success_r0_advance_error","success_r0_begin_error","success_r0_end_error","success_r0_bad_order","success_r0_bad_kind",
        "success_dispose_callback",
        "failure_callback_error","failure_wrong_callback","failure_null_callback","failure_submit_error","failure_inline_then_throw",
        "failure_duplicate_inline","failure_context_error","failure_terminate_in_submit","failure_terminate_in_matrix","failure_duplicate_in_matrix","failure_dispose_error",
        "request_identity","request_sender_and_error","request_repeated_submit","request_after_dispose","request_null_callback","request_context_rejected",
        "request_clone_preserves_owner","request_late_callback_ignored","request_dispose_throws_once","request_dispose_during_submit_rejected",
        "factory_clone_preserves_owner","cursor_clone_preserves_owner","native_identity_preserved","factory_duplicate_slot_rejected",
        "factory_reuse_construction_rejected","factory_foreign_control_rejected","factory_invalidation",
        "native_query_kind_changed","native_query_ticks_changed","native_query_inclusion_changed",
        "bounds_before_advance_rejected","bounds_after_false_rejected","end_before_begin_rejected","duplicate_begin_rejected",
        "ordinary_cursor_reuse_rejected","request_and_factory_dependencies","checkpoint_blocks_constructor",
        "reentrant_native_call_stops_matrix","pending_termination"
    };
    public static int Main(string[] args)
    {
        if(args.Length==3 && args[0]=="--emit")
        {
            Check(Array.IndexOf(Cases,"success_"+args[2])>=0,"UNKNOWN_EMIT_MODE");Success(args[1],args[2]);
            Console.WriteLine("{\"classification\":\"SYNTHETIC_SDK_BRIDGE_ONLY\",\"sealed\":true}");return 0;
        }
        if(args.Length<2)return 2;
        string root=args[1];int pass=0,fail=0;var results=new List<object>();
        foreach(string name in Cases)
        {
            if(args[0]!="--all" && !(args[0]=="--case" && args.Length==3 && args[2]==name))continue;
            try { MainCase(root,name);results.Add(new { name=name,status="PASS",detail="NONE" });pass++; }
            catch(Exception error) { results.Add(new { name=name,status="FAIL",detail=error.GetType().Name+":"+error.Message });fail++; }
        }
        Console.WriteLine(new JavaScriptSerializer().Serialize(new {
            classification="SYNTHETIC_SDK_BRIDGE_ONLY",total=pass+fail,passed=pass,failed=fail,
            real_native_api_calls=0,loaded_ninjatrader_assemblies=Array.FindAll(AppDomain.CurrentDomain.GetAssemblies(),
                a=>a.GetName().Name.StartsWith("NinjaTrader",StringComparison.Ordinal)).Length,results=results }));
        return fail==0 && pass>0?0:1;
    }
}
