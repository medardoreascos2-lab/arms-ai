// Synthetic C# 5 request/resource lifecycle harness. No NinjaTrader assemblies loaded.
using System;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using System.Threading;
using System.Web.Script.Serialization;
using Arms.AI.Diagnostics.R53;

internal static class LifecycleHarness
{
    private const string Secret="PRIVATE_NATIVE_SENTINEL";
    private static void Assert(bool value, string id) { if(!value) throw new Exception(id); }
    private sealed class Writer : IDisposable
    {
        internal int Writes, Closes;
        internal bool Closed;
        internal Action OnWrite, OnClose;
        internal void Write()
        {
            Assert(!Closed,"writer_used_after_close"); Writes++;
            if(OnWrite != null) OnWrite();
        }
        public void Dispose()
        {
            Closes++; Assert(Closes==1,"writer_double_dispose");
            if(OnClose != null) OnClose(); Closed=true;
        }
    }
    private sealed class Request : ISessionTimestampRequestV1
    {
        internal object Id=new object();
        internal bool IdentityThrows;
        internal int Submits, Closes;
        internal Action OnSubmit, OnClose;
        internal Action<object,bool> Callback;
        public object Identity { get { if(IdentityThrows) throw new IOException(Secret); return Id; } }
        public void Submit(Action<object,bool> callback)
        {
            Assert(Closes==0,"request_used_after_close"); Submits++; Callback=callback;
            if(OnSubmit != null) OnSubmit();
        }
        internal void Fire() { Callback(Id,true); }
        public void Dispose()
        {
            Closes++; Assert(Closes==1,"request_double_dispose");
            if(OnClose != null) OnClose();
        }
    }
    private sealed class Cursor : ISessionTimestampCursor
    {
        private readonly object id=new object();
        private readonly Flow flow;
        internal Cursor(Flow f) { flow=f; }
        public object Identity { get { return id; } }
        public bool Advance(DateTime query,bool include)
        {
            Assert(flow.R.Closes==0 && !flow.W.Closed,"closed_during_native_action");
            flow.Calls++; if(flow.OnAdvance != null) flow.OnAdvance();
            return flow.Returned;
        }
        public DateTime ReadBegin()
        { Assert(flow.Returned,"begin_after_false"); return new DateTime(2026,9,13,22,0,0,DateTimeKind.Utc); }
        public DateTime ReadEnd()
        { Assert(flow.Returned,"end_after_false"); return new DateTime(2026,9,14,21,0,0,DateTimeKind.Utc); }
    }
    private sealed class Flow
    {
        internal object Owner=new object();
        internal SessionTimestampLifecycleV1 Life;
        internal Writer W=new Writer();
        internal Request R=new Request();
        internal int WFactories,RFactories,Processes,Prepares,Calls,Constructors;
        internal bool Returned=true;
        internal Action OnAdvance;
        internal Action<string> OnCheck;
        internal Func<IDisposable> WriterFactory;
        internal Func<ISessionTimestampRequestV1> RequestFactory;
        internal Func<ISessionTimestampRequestV1,Action,TimestampMatrixReport> Processor;
        internal Action<TimestampMatrixReport> Prepare;
        internal Flow()
        {
            Life=new SessionTimestampLifecycleV1(Owner);
            WriterFactory=()=>{ WFactories++; return W; };
            RequestFactory=()=>{ RFactories++; return R; };
            Processor=RunMatrix;
            Prepare=report=>{
                Assert(Life.Inspect(Owner).SubmitReturned,"prepare_before_submit_return");
                Assert(R.Closes==0 && !W.Closed,"prepare_closed_resources");
                Assert(report.MatrixCompleted,"prepare_incomplete_matrix");
                Prepares++; W.Write();
            };
        }
        internal TimestampMatrixReport RunMatrix(ISessionTimestampRequestV1 r, Action checkpoint)
        {
            Processes++; checkpoint(); Assert(Object.ReferenceEquals(r,R),"processor_wrong_request");
            var plan=SessionTimestampPlanV1.Build(new DateTime(2026,9,15,22,1,0,DateTimeKind.Unspecified),
                new DateTime(2026,9,21,21,0,0,DateTimeKind.Unspecified),5520,
                new string('a',64),new string('b',64),TimeZoneInfo.Utc);
            var executor=new SessionTimestampExecutorV1();
            return executor.Execute(plan,c=>{ Constructors++; return new Cursor(this); },(phase,c)=>checkpoint());
        }
        internal void Start(bool enabled=true)
        {
            Life.Start(Owner,enabled,WriterFactory,RequestFactory,Processor,Prepare,
                phase=>{ if(OnCheck != null) OnCheck(phase); });
        }
        internal TimestampLifecycleSnapshot State() { return Life.Inspect(Owner); }
    }
    private static void Pass(Flow f)
    {
        var s=f.State();
        Assert(s.Status=="READY_FOR_SEAL_NOT_SEALED" && s.ReadyForSeal,"not_ready");
        Assert(s.StopGuard=="NONE" && s.ExceptionType=="NONE","unexpected_guard");
        Assert(s.ResourcesReleased && s.RequestClosed && s.WriterClosed,"resources_not_closed");
        Assert(s.WriterFactoryAttempts==1 && s.RequestFactoryAttempts==1 && s.SubmitAttempts==1,"factory_counts");
        Assert(s.ProcessAttempts==1 && s.PreparationAttempts==1,"process_counts");
        Assert(f.R.Closes==1 && f.W.Closes==1 && s.RequestDisposeAttempts==1 && s.WriterDisposeAttempts==1,"dispose_counts");
        Assert(s.Matrix!=null && s.Matrix.MatrixCompleted,"matrix_missing");
        Assert(!s.SealWritten && !s.NativeProvenanceAttested && !s.HistoricalAdmission,"authority_claim");
    }
    private static void Fail(Flow f,string guard)
    {
        var s=f.State();
        Assert(s.Status=="FAILED_CLOSED" && s.StopGuard==guard,"wrong_guard:"+s.StopGuard+":"+guard);
        Assert(!s.ReadyForSeal && !s.SealWritten && !s.NativeProvenanceAttested,"false_ready");
        Assert(s.ResourcesReleased,"release_not_attempted");
        Assert(f.R.Closes<=1 && f.W.Closes<=1,"double_close");
    }
    private static void ExpectOwner(Action call)
    {
        try { call(); throw new Exception("owner_not_rejected"); }
        catch(LifecycleGuardException e) { Assert(e.GuardId=="LIFECYCLE_NOT_OWNER","wrong_owner_guard"); }
    }
    private static void Normal() { var f=new Flow(); f.Start(); Assert(!f.State().ReadyForSeal,"early_ready"); f.R.Fire(); Pass(f); Assert(f.Calls==12 && f.Constructors==11,"budget"); }
    private static void AllFalse() { var f=new Flow(); f.Returned=false; f.Start(); f.R.Fire(); Pass(f); Assert(f.Calls==11 && f.Constructors==11,"false_budget"); }
    private static void Inline()
    {
        var f=new Flow(); f.R.OnSubmit=()=>{ f.R.Fire(); Assert(f.Prepares==0 && !f.State().ReadyForSeal,"inline_early_prepare"); };
        f.Start(); Pass(f);
    }
    private static void InlineThrows()
    {
        var f=new Flow(); f.R.OnSubmit=()=>{ f.R.Fire(); throw new IOException(Secret); };
        f.Start(); Fail(f,"REQUEST_SUBMIT"); Assert(f.Prepares==0,"seal_after_submit_throw");
    }
    private static void Async()
    {
        var f=new Flow(); f.Start(); Exception fault=null;
        var t=new Thread(()=>{try{f.R.Fire();}catch(Exception e){fault=e;}}); t.Start();
        Assert(t.Join(5000),"async_timeout"); Assert(fault==null,"async_exception"); Pass(f);
    }
    private static void CrossThreadInline()
    {
        var f=new Flow(); Exception fault=null;
        f.R.OnSubmit=()=>{var t=new Thread(()=>{try{f.R.Fire();}catch(Exception e){fault=e;}});t.Start();
            Assert(t.Join(5000),"submit_callback_deadlock"); Assert(f.Prepares==0,"early_cross_thread_prepare");};
        f.Start(); Assert(fault==null,"callback_exception"); Pass(f);
    }
    private static void Disabled()
    {
        var f=new Flow(); f.Start(false); Assert(f.State().Status=="IDLE_DISABLED","disabled_status");
        Assert(f.WFactories==0 && f.RFactories==0 && f.R.Submits==0,"disabled_side_effect");
        f.Start(); f.R.Fire(); Pass(f);
    }
    private static void Pending()
    {
        var f=new Flow(); f.Start(); Assert(f.State().Status=="PENDING" && f.R.Closes==0,"pending_closed");
        f.Life.Terminate(f.Owner); Fail(f,"TERMINATED_INCOMPLETE"); Assert(f.Prepares==0,"pending_prepared");
    }
    private static void TerminatedBeforeStart()
    {
        var f=new Flow(); f.Life.Terminate(f.Owner); Fail(f,"TERMINATED_BEFORE_START");
        try{f.Start();throw new Exception("start_after_termination");}catch(LifecycleGuardException){}
        Assert(f.RFactories==0 && f.WFactories==0,"created_after_termination");
    }
    private static void TerminateDuringProcess()
    {
        var f=new Flow(); f.OnAdvance=()=>{f.Life.Terminate(f.Owner);Assert(f.R.Closes==0,"disposed_in_flight");};
        f.Start();f.R.Fire();Fail(f,"TERMINATED_INCOMPLETE");Assert(f.Calls==1 && f.Prepares==0,"more_calls_after_termination");
    }
    private static void TerminateDuringSubmit()
    {
        var f=new Flow();f.R.OnSubmit=()=>{f.Life.Terminate(f.Owner);Assert(f.R.Closes==0,"dispose_inside_submit");};
        f.Start();Fail(f,"TERMINATED_INCOMPLETE");Assert(f.Prepares==0,"prepare_after_terminate");
    }
    private static void TerminateDuringFactory()
    {
        var f=new Flow(); f.RequestFactory=()=>{f.RFactories++;f.Life.Terminate(f.Owner);return f.R;};
        f.Start();Fail(f,"TERMINATED_INCOMPLETE");Assert(f.R.Submits==0 && f.R.Closes==1,"late_factory_resource_leak");
    }
    private static void DuplicateInline()
    {
        var f=new Flow();f.R.OnSubmit=()=>{f.R.Fire();f.R.Fire();};f.Start();
        Fail(f,"CALLBACK_DUPLICATE_BEFORE_RELEASE");Assert(f.Processes==1 && f.Prepares==0,"duplicate_processed");
    }
    private static void DuplicateReentrant()
    {
        var f=new Flow();f.OnAdvance=()=>f.R.Fire();f.Start();f.R.Fire();
        Fail(f,"CALLBACK_DUPLICATE_BEFORE_RELEASE");Assert(f.Calls==1 && f.Processes==1,"reentrant_more_work");
    }
    private static void DuplicateConcurrent()
    {
        var f=new Flow(); Exception fault=null;
        using(var entered=new ManualResetEvent(false)) using(var proceed=new ManualResetEvent(false))
        {
            f.OnAdvance=()=>{entered.Set();Assert(proceed.WaitOne(5000),"proceed_timeout");};f.Start();
            var t=new Thread(()=>{try{f.R.Fire();}catch(Exception e){fault=e;}});t.Start();
            try {Assert(entered.WaitOne(5000),"enter_timeout");f.R.Fire();Assert(f.R.Closes==0,"concurrent_close_in_use");}
            finally {proceed.Set();Assert(t.Join(5000),"join_timeout");}
        }
        Assert(fault==null,"concurrent_fault");Fail(f,"CALLBACK_DUPLICATE_BEFORE_RELEASE");Assert(f.Calls==1,"second_native_call");
    }
    private static void LateCallbacks()
    {
        var f=new Flow();f.Start();f.R.Fire();for(int i=0;i<20;i++)f.R.Fire();f.Life.Terminate(f.Owner);Pass(f);
        Assert(f.Calls==12 && f.State().DuplicateCallbacks==0,"late_mutation");
    }
    private static void DisposeCallback()
    {
        var f=new Flow(); f.R.OnClose=()=>f.R.Fire(); f.Start(); f.R.Fire(); Pass(f); Assert(f.Processes==1,"dispose_callback_reused");
    }
    private static void CallbackError() {var f=new Flow();f.Start();f.R.Callback(f.R.Id,false);Fail(f,"CALLBACK_ERROR");Assert(f.Processes==0,"processed_error");}
    private static void WrongCallback() {var f=new Flow();f.Start();f.R.Callback(new object(),true);Fail(f,"CALLBACK_IDENTITY_MISMATCH");}
    private static void EarlyCallback() {var f=new Flow();f.Life.Callback(f.Owner,new object(),true);Fail(f,"CALLBACK_BEFORE_SUBMIT");Assert(f.WFactories==0,"early_factory");}
    private static void MissingIdentity() {var f=new Flow();f.R.Id=null;f.Start();Fail(f,"REQUEST_IDENTITY_MISSING");Assert(f.R.Submits==0,"submit_missing_id");}
    private static void IdentityThrows() {var f=new Flow();f.R.IdentityThrows=true;f.Start();Fail(f,"REQUEST_IDENTITY");}
    private static void IdentityChanged()
    {var f=new Flow();f.Start();var original=f.R.Id;f.R.Id=new object();f.R.Callback(original,true);Fail(f,"REQUEST_IDENTITY_CHANGED");}
    private static void IdentityAfterProcess()
    {var f=new Flow();f.Processor=(r,c)=>{var m=f.RunMatrix(r,c);f.R.Id=new object();return m;};f.Start();f.R.Fire();Fail(f,"REQUEST_IDENTITY_CHANGED");}
    private static void WriterFactoryThrow() {var f=new Flow();f.WriterFactory=()=>{throw new IOException(Secret);};f.Start();Fail(f,"WRITER_FACTORY");Assert(f.RFactories==0,"request_after_writer_error");}
    private static void WriterFactoryNull() {var f=new Flow();f.WriterFactory=()=>null;f.Start();Fail(f,"WRITER_FACTORY_RETURNED_NULL");}
    private static void RequestFactoryThrow() {var f=new Flow();f.RequestFactory=()=>{throw new IOException(Secret);};f.Start();Fail(f,"REQUEST_FACTORY");Assert(f.W.Closes==1,"writer_leak");}
    private static void RequestFactoryNull() {var f=new Flow();f.RequestFactory=()=>null;f.Start();Fail(f,"REQUEST_FACTORY_RETURNED_NULL");Assert(f.W.Closes==1,"writer_leak");}
    private static void ResourceAlias() {var f=new Flow();f.WriterFactory=()=>f.R;f.Start();Fail(f,"RESOURCE_ALIAS");Assert(f.R.Closes==1 && f.State().WriterDisposeAttempts==0,"alias_double_close");}
    private static void SubmitThrow() {var f=new Flow();f.R.OnSubmit=()=>{throw new IOException(Secret);};f.Start();Fail(f,"REQUEST_SUBMIT");Assert(f.Prepares==0,"prepare_after_submit_throw");}
    private static void ProcessorThrow() {var f=new Flow();f.Processor=(r,c)=>{throw new IOException(Secret);};f.Start();f.R.Fire();Fail(f,"PROCESSOR");}
    private static void ProcessorNull() {var f=new Flow();f.Processor=(r,c)=>null;f.Start();f.R.Fire();Fail(f,"MATRIX_INCOMPLETE");}
    private static void MatrixIncomplete()
    {var f=new Flow();f.Processor=(r,c)=>new SessionTimestampExecutorV1().Execute(null,x=>new Cursor(f),(p,x)=>c());f.Start();f.R.Fire();Fail(f,"MATRIX_INCOMPLETE");}
    private static void PrepareThrow() {var f=new Flow();f.W.OnWrite=()=>{throw new IOException(Secret);};f.Start();f.R.Fire();Fail(f,"EVIDENCE_PREPARATION");Assert(f.W.Closes==1,"close_after_prepare_fault");}
    private static void RequestDisposeThrow() {var f=new Flow();f.R.OnClose=()=>{throw new IOException(Secret);};f.Start();f.R.Fire();Fail(f,"REQUEST_DISPOSE");Assert(f.W.Closes==1 && !f.State().RequestClosed,"dispose_lie");}
    private static void WriterDisposeThrow() {var f=new Flow();f.W.OnClose=()=>{throw new IOException(Secret);};f.Start();f.R.Fire();Fail(f,"WRITER_DISPOSE");Assert(!f.State().WriterClosed,"writer_closed_lie");}
    private static void BothDisposeThrow()
    {var f=new Flow();f.R.OnClose=()=>{throw new IOException(Secret);};f.W.OnClose=()=>{throw new IOException(Secret);};f.Start();f.R.Fire();Fail(f,"REQUEST_DISPOSE");Assert(!f.State().WriterClosed && !f.State().RequestClosed,"closed_on_error");}
    private static void ContextFailure(string phase)
    {
        var f=new Flow();f.OnCheck=p=>{if(p==phase)throw new IOException(Secret);};f.Start();
        if(f.R.Callback!=null)f.R.Fire();Fail(f,"CONTEXT_"+phase);
    }
    private static void TerminateDuringPrepare() {var f=new Flow();f.W.OnWrite=()=>f.Life.Terminate(f.Owner);f.Start();f.R.Fire();Fail(f,"TERMINATED_INCOMPLETE");}
    private static void TerminateDuringDispose() {var f=new Flow();f.R.OnClose=()=>f.Life.Terminate(f.Owner);f.Start();f.R.Fire();Fail(f,"TERMINATED_INCOMPLETE");}
    private static void ReentrantStart()
    {
        var f=new Flow();f.R.OnSubmit=()=>{try{f.Start();}catch(LifecycleGuardException){}};
        f.Start();Fail(f,"START_REENTRANT_OR_REPEATED");Assert(f.RFactories==1 && f.R.Submits==1,"start_retry");
    }
    private static void RepeatAfterComplete()
    {var f=new Flow();f.Start();f.R.Fire();try{f.Start();throw new Exception("repeat_start_allowed");}catch(LifecycleGuardException){}Pass(f);Assert(f.RFactories==1,"repeat_factory");}
    private static void RepeatPending()
    {var f=new Flow();f.Start();try{f.Start();throw new Exception("repeat_pending_allowed");}catch(LifecycleGuardException){}Fail(f,"START_REENTRANT_OR_REPEATED");Assert(f.R.Closes==1 && f.W.Closes==1,"pending_repeat_leak");}
    private static void NullOwner()
    {try{new SessionTimestampLifecycleV1(null);throw new Exception("null_owner_allowed");}catch(ArgumentNullException){}}
    private static void WrongOwner()
    {
        var f=new Flow();f.Start();var other=new object();
        ExpectOwner(()=>f.Life.Terminate(other));ExpectOwner(()=>f.Life.Callback(other,f.R.Id,true));
        ExpectOwner(()=>f.Life.Start(other,true,f.WriterFactory,f.RequestFactory,f.Processor,f.Prepare,p=>{}));
        ExpectOwner(()=>f.Life.Inspect(other));Assert(f.R.Closes==0 && f.W.Closes==0,"foreign_disposed_owner");f.R.Fire();Pass(f);
    }
    private static void CoreClone()
    {
        var f=new Flow();f.Start();
        var clone=(SessionTimestampLifecycleV1)typeof(object).GetMethod("MemberwiseClone",BindingFlags.Instance|BindingFlags.NonPublic).Invoke(f.Life,null);
        Assert(!clone.IsOwner(f.Owner),"clone_is_owner");ExpectOwner(()=>clone.Terminate(f.Owner));
        ExpectOwner(()=>clone.Callback(f.Owner,f.R.Id,true));Assert(f.R.Closes==0,"clone_closed_request");f.R.Fire();Pass(f);
    }
    private sealed class Host
    {
        internal SessionTimestampLifecycleV1 Run;
        internal Host Copy(){return (Host)MemberwiseClone();}
        internal void End(){if(Run!=null && Run.IsOwner(this))Run.Terminate(this);}
    }
    private static void HostClone()
    {
        var h=new Host();var f=new Flow();f.Owner=h;f.Life=new SessionTimestampLifecycleV1(h);h.Run=f.Life;f.Start();
        var copy=h.Copy();copy.End();Assert(f.R.Closes==0 && f.W.Closes==0,"UI_clone_destroyed_original");f.R.Fire();Pass(f);
    }
    private static void MissingDependencies()
    {
        for(int k=0;k<5;k++)
        {
            var f=new Flow();f.Life.Start(f.Owner,true,k==0?null:f.WriterFactory,k==1?null:f.RequestFactory,
                k==2?null:f.Processor,k==3?null:f.Prepare,k==4?null:(Action<string>)(p=>{}));
            Fail(f,"DEPENDENCIES_MISSING");Assert(f.WFactories==0 && f.RFactories==0,"dependency_side_effect");
        }
    }
    private static void Redaction()
    {
        var f=new Flow();f.Processor=(r,c)=>{throw new IOException(Secret);};f.Start();f.R.Fire();
        string data=new JavaScriptSerializer().Serialize(f.State());Assert(!data.Contains(Secret),"secret_leaked");Fail(f,"PROCESSOR");
    }
    private static void IndependentOwners()
    {var a=new Flow();var b=new Flow();a.Start();b.Start();a.Life.Terminate(a.Owner);Fail(a,"TERMINATED_INCOMPLETE");Assert(b.R.Closes==0,"cross_close");b.R.Fire();Pass(b);}
    private sealed class Test {internal string Name;internal Action Body;internal Test(string n,Action a){Name=n;Body=a;}}
    private static Test[] Tests()
    {
        return new[] {
            new Test("normal_matrix_then_release",Normal),new Test("all_false_still_diagnostic",AllFalse),
            new Test("inline_waits_for_submit_return",Inline),new Test("inline_then_throw_never_prepares",InlineThrows),
            new Test("async_callback",Async),new Test("callback_other_thread_during_submit_no_deadlock",CrossThreadInline),
            new Test("disabled_creates_nothing_then_enabled",Disabled),new Test("pending_then_terminate",Pending),
            new Test("terminate_before_start",TerminatedBeforeStart),new Test("terminate_during_process_cooperative",TerminateDuringProcess),
            new Test("terminate_during_submit_deferred_dispose",TerminateDuringSubmit),new Test("terminate_during_factory_no_leak",TerminateDuringFactory),
            new Test("duplicate_inline_prevents_completion",DuplicateInline),new Test("duplicate_reentrant_stops_next_call",DuplicateReentrant),
            new Test("duplicate_concurrent_preserves_inflight_resources",DuplicateConcurrent),new Test("late_callbacks_no_more_work",LateCallbacks),
            new Test("callback_from_dispose_ignored",DisposeCallback),new Test("callback_error_rejected",CallbackError),
            new Test("foreign_request_callback_rejected",WrongCallback),new Test("callback_before_submit_rejected",EarlyCallback),
            new Test("request_identity_null",MissingIdentity),new Test("request_identity_throws",IdentityThrows),
            new Test("request_identity_changed",IdentityChanged),new Test("request_identity_after_process_changed",IdentityAfterProcess),
            new Test("writer_factory_throws",WriterFactoryThrow),new Test("writer_factory_null",WriterFactoryNull),
            new Test("request_factory_throws_closes_writer",RequestFactoryThrow),new Test("request_factory_null_closes_writer",RequestFactoryNull),
            new Test("request_writer_alias_disposed_once",ResourceAlias),new Test("submit_throws",SubmitThrow),
            new Test("processor_throws",ProcessorThrow),new Test("processor_null",ProcessorNull),
            new Test("incomplete_matrix_rejected",MatrixIncomplete),new Test("prepare_throws",PrepareThrow),
            new Test("request_dispose_failure_never_ready",RequestDisposeThrow),new Test("writer_dispose_failure_never_ready",WriterDisposeThrow),
            new Test("both_dispose_failures_attempted_once",BothDisposeThrow),
            new Test("context_before_open",()=>ContextFailure("BEFORE_OPEN")),
            new Test("context_before_request_create",()=>ContextFailure("BEFORE_REQUEST_CREATE")),
            new Test("context_before_submit",()=>ContextFailure("BEFORE_SUBMIT")),
            new Test("context_after_submit",()=>ContextFailure("AFTER_SUBMIT")),
            new Test("context_before_process",()=>ContextFailure("BEFORE_PROCESS")),
            new Test("context_after_process",()=>ContextFailure("AFTER_PROCESS")),
            new Test("context_before_prepare",()=>ContextFailure("BEFORE_PREPARE")),
            new Test("context_after_prepare",()=>ContextFailure("AFTER_PREPARE")),
            new Test("terminate_during_prepare",TerminateDuringPrepare),new Test("terminate_during_dispose",TerminateDuringDispose),
            new Test("reentrant_start_not_retried",ReentrantStart),new Test("repeat_after_complete_no_mutation",RepeatAfterComplete),
            new Test("repeated_pending_start_releases_once",RepeatPending),new Test("null_owner_rejected",NullOwner),
            new Test("wrong_owner_cannot_touch_resources",WrongOwner),new Test("shallow_core_clone_preserves_original",CoreClone),
            new Test("shallow_UI_host_clone_preserves_original",HostClone),new Test("all_missing_dependency_positions",MissingDependencies),
            new Test("safe_error_redaction",Redaction),new Test("independent_owners_no_cross_dispose",IndependentOwners)
        };
    }
    public static int Main(string[] args)
    {
        bool all=args.Length==1 && args[0]=="--all";
        if(!all && !(args.Length==2 && args[0]=="--case"))return 2;
        int passed=0,failed=0;var rows=new List<object>();
        foreach(var test in Tests())
        {
            if(!all && test.Name!=args[1])continue;
            try{test.Body();rows.Add(new{name=test.Name,status="PASS",detail="NONE"});passed++;}
            catch(Exception error){rows.Add(new{name=test.Name,status="FAIL",detail=error.GetType().Name+":"+error.Message});failed++;}
        }
        Console.WriteLine(new JavaScriptSerializer().Serialize(new {
            classification="SYNTHETIC_LIFECYCLE_ONLY_NOT_NATIVE_EVIDENCE",total=passed+failed,passed=passed,failed=failed,
            real_native_api_calls=0,seal_files_written=0,native_provenance_attested=false,
            loaded_ninjatrader_assemblies=Array.FindAll(AppDomain.CurrentDomain.GetAssemblies(),a=>a.GetName().Name.StartsWith("NinjaTrader",StringComparison.Ordinal)).Length,
            results=rows}));
        return failed==0 && passed>0 ? 0 : 1;
    }
}
