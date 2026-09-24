// R5.3-H integration: actual indicator and A-G with F1's explicit SDK doubles.
// Compile with /main:NativeProbeHarness. No real NinjaTrader assembly is loaded.
using System;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using System.Security.Cryptography;
using System.Text;
using System.Threading;
using System.Web.Script.Serialization;
using Arms.AI.Diagnostics.R53;
using NinjaTrader.Data;
using NinjaTrader.NinjaScript;

namespace NinjaTrader.NinjaScript
{
    public enum State { SetDefaults,Configure,DataLoaded,Historical,Transition,Realtime,Terminated }
    [AttributeUsage(AttributeTargets.Property)]public sealed class NinjaScriptPropertyAttribute:Attribute { }
}
namespace NinjaTrader.NinjaScript.Indicators
{
    public class Indicator
    {
        public State State;public string Name,Description;public bool IsOverlay,IsChartOnly;
        public Bars Bars;public readonly List<string> Output=new List<string>();
        protected virtual void OnStateChange() { }
        protected virtual void OnBarUpdate() { }
        protected void Print(object text) { Output.Add(text.ToString()); }
    }
    public sealed class NativeProbeHost:ArmsSessionTimestampInterpretationProbeV1
    {
        public void Step(State state) { State=state;OnStateChange(); }
        public void Bar() { OnBarUpdate(); }
        public NativeProbeHost Shallow() { return (NativeProbeHost)MemberwiseClone(); }
    }
}

internal static class NativeProbeHarness
{
    const string Secret="PRIVATE_PROVIDER_SENTINEL";
    static void Check(bool value,string code) { if(!value)throw new Exception(code); }
    static void Reset(string mode)
    {
        NinjaTrader.Cbi.Instrument.Next=new NinjaTrader.Cbi.Instrument();NinjaTrader.Cbi.Connection.PlaybackConnection=null;
        NinjaTrader.Core.Globals.GeneralOptions=new NinjaTrader.Core.Options();TradingHours.Next=new TradingHours();
        BarsRequest.Last=null;BarsRequest.TotalCreates=0;BarsRequest.ThrowConstructor=false;BarsRequest.ThrowConfiguration=false;
        BarsRequest.AfterConstruct=null;BarsRequest.NextMode=mode;
        if(mode=="irrelevant_exceptions")TradingHours.Next.Holidays.Add(new DateTime(2026,1,1),Secret);
    }
    static string Fresh(string root,string name)
    { string path=Path.Combine(root,name+"-"+Guid.NewGuid().ToString("N"));Directory.CreateDirectory(path);return path; }
    static string Contents(string folder)
    {
        if(!Directory.Exists(folder))return "ABSENT";
        string[] files=Directory.GetFiles(folder,"*",SearchOption.AllDirectories);Array.Sort(files,StringComparer.Ordinal);
        var text=new StringBuilder();using(var h=SHA256.Create())foreach(var f in files)
        {
            // Pending-owner checks read an already-open writer. Share its existing write access;
            // this reader remains read-only and never changes the production writer's policy.
            using(var input=new FileStream(f,FileMode.Open,FileAccess.Read,FileShare.ReadWrite))
                text.Append(f.Substring(folder.Length)).Append('|').Append(BitConverter.ToString(h.ComputeHash(input)));
        }
        return text.ToString();
    }
    static NinjaTrader.NinjaScript.Indicators.NativeProbeHost NewHost(string folder,bool enabled)
    {
        var h=new NinjaTrader.NinjaScript.Indicators.NativeProbeHost();h.Step(State.SetDefaults);
        Check(!h.ProbeEnabled && h.OutputDirectory=="" && !h.MarketReopenConfirmed && !h.NqDataFlowConfirmed && !h.ConnectionStableConfirmed,"DEFAULT_GATES");
        h.Bars=new Bars { Instrument=new NinjaTrader.Cbi.Instrument(),BarsPeriod=new BarsPeriod {
            BarsPeriodType=BarsPeriodType.Minute,Value=1,MarketDataType=MarketDataType.Last },TradingHours=new TradingHours() };
        h.ProbeEnabled=enabled;h.OutputDirectory=folder;
        h.MarketReopenConfirmed=enabled;h.NqDataFlowConfirmed=enabled;h.ConnectionStableConfirmed=enabled;
        return h;
    }
    static string Seal(string folder) { return Path.Combine(folder,SessionTimestampContextEnvelopeV1.SealName); }
    static void CheckSealed(NinjaTrader.NinjaScript.Indicators.NativeProbeHost h,string folder,BarsRequest raw)
    {
        var state=h.InspectDiagnostic();Check(state.Sealed && state.Status=="SEALED_DIAGNOSTIC_ONLY" && state.PublicationAttempts==1,"HOST_NOT_SEALED:"+state.Guard+":"+state.ExceptionType);
        Check(state.Lifecycle!=null && state.Lifecycle.ReadyForSeal && state.Lifecycle.ResourcesReleased,"LIFECYCLE_NOT_RELEASED");
        Check(raw!=null && raw.Invokes==1 && raw.Disposes==1,"REQUEST_NOT_CLOSED_ONCE");
        var report=state.Lifecycle.Matrix;
        Check(report.MatrixCompleted && report.Observations.Count==12 && raw.Bars.Creates==report.ConstructorAttempts && raw.Bars.Calls==report.CallAttempts,"MATRIX_COUNTS");
        Check(raw.Bars.Creates<=11 && raw.Bars.Calls<=12 && raw.Bars.Begins==report.BeginReadAttempts && raw.Bars.Ends==report.EndReadAttempts,"BUDGET");
        Check(File.Exists(Seal(folder)) && Directory.GetFiles(folder,"*",SearchOption.AllDirectories).Length==4,"ENVELOPE_MISSING");
        foreach(string f in Directory.GetFiles(folder,"*",SearchOption.AllDirectories))Check(!File.ReadAllText(f).Contains(Secret),"PRIVATE_TEXT_LEAK");
        Check(h.Output.Count==1 && h.Output[0].Contains("SEALED_DIAGNOSTIC_ONLY") && !h.Output[0].Contains(Secret),"SAFE_NOTIFICATION");
        int reads=raw.Bars.TimeReads,calls=raw.Bars.Calls;string before=Contents(folder);
        h.Bar();h.Step(State.DataLoaded);h.Step(State.Configure);h.Step(State.Historical);h.Step(State.Transition);h.Step(State.Realtime);
        h.Step(State.Terminated);raw.Fire();h.Step(State.DataLoaded);
        Check(raw.Disposes==1 && reads==raw.Bars.TimeReads && calls==raw.Bars.Calls && before==Contents(folder),"LATE_ACTIVITY_CHANGED_RESULT");
        Check(h.Output.Count==1,"REPEATED_NOTIFICATION");
    }
    static void Settings(BarsRequest raw,string mode,NinjaTrader.NinjaScript.Indicators.NativeProbeHost h)
    {
        raw.AfterBars=()=> {
            if(mode=="mixed" || mode=="duplicate" || mode=="decreasing" || mode=="misaligned")raw.Bars.DataMode=mode;
            if(mode=="rows4503")raw.Bars.Count=4503;if(mode=="rows5520")raw.Bars.Count=5520;if(mode=="rows10002")raw.Bars.Count=10002;
            if(mode=="first_utc")raw.Bars.DataMode="first_utc";
            if(mode=="snapshot_mutation")raw.Bars.OnAdvance=()=>raw.Bars.ChangedPrice=true;
            if(mode=="count_mutation")raw.Bars.CountMutation=true;
            if(mode=="gettime_error")raw.Bars.ThrowTime=true;
            if(mode=="ohlc_error")raw.Bars.ThrowOhlc=true;
            if(mode=="wrong_returned_template")raw.Bars.TradingHours=new TradingHours { Name="OTHER" };
            if(mode=="duplicate_in_matrix")raw.Bars.OnAdvance=()=>raw.Fire();
            if(mode=="terminate_in_matrix")raw.Bars.OnAdvance=()=>h.Step(State.Terminated);
            if(mode=="gate_in_matrix")raw.Bars.OnAdvance=()=>h.NqDataFlowConfirmed=false;
            if(mode=="output_in_matrix")raw.Bars.OnAdvance=()=>h.OutputDirectory="OTHER";
            if(mode=="chart_in_matrix")raw.Bars.OnAdvance=()=>h.Bars=new Bars();
            if(mode=="policy_in_matrix")raw.Bars.OnAdvance=()=>raw.LookupPolicy=NinjaTrader.Cbi.LookupPolicies.Provider;
            if(mode=="playback_in_matrix")raw.Bars.OnAdvance=()=>NinjaTrader.Cbi.Connection.PlaybackConnection=new NinjaTrader.Cbi.Connection();
            if(mode=="timezone_in_matrix")raw.Bars.OnAdvance=()=>NinjaTrader.Core.Globals.GeneralOptions.TimeZoneInfo=TradingHours.Next.TimeZoneInfo;
            if(mode=="foreign_before_prepare")raw.Bars.OnAdvance=()=>File.WriteAllText(Path.Combine(h.OutputDirectory,"foreign.txt"),"KEEP");
        };
        if(mode=="dispose_callback")raw.OnDispose=()=>raw.Fire();
        if(mode=="request_dispose_error")raw.OnDispose=()=> { throw new InvalidOperationException(Secret); };
        if(mode=="output_on_dispose")raw.OnDispose=()=>h.OutputDirectory="OTHER";
        if(mode=="terminate_on_dispose")raw.OnDispose=()=>h.Step(State.Terminated);
        if(mode=="tamper_on_dispose")raw.OnDispose=()=>File.AppendAllText(Path.Combine(h.OutputDirectory,SessionTimestampContextEnvelopeV1.ContextName)," ");
        if(mode=="foreign_on_dispose")raw.OnDispose=()=>File.WriteAllText(Path.Combine(h.OutputDirectory,"foreign.txt"),"KEEP");
    }
    static void Success(string folder,string mode)
    {
        Reset(mode);string capture=Path.Combine(folder,"capture");Directory.CreateDirectory(capture);var h=NewHost(capture,true);
        BarsRequest.AfterConstruct=()=>Settings(BarsRequest.Last,mode,h);
        h.Step(State.Configure);h.Step(State.DataLoaded);var raw=BarsRequest.Last;
        Check(raw!=null,"NO_REQUEST");
        if(mode=="clone_active" || mode=="clone_setdefaults")
        {
            var clone=h.Shallow();string before=Contents(capture);
            if(mode=="clone_setdefaults")clone.Step(State.SetDefaults);
            clone.Step(State.Terminated);clone.Step(State.DataLoaded);
            Check(raw.Disposes==0 && before==Contents(capture) && h.ProbeEnabled,"CLONE_DAMAGED_OWNER");
            Check(clone.InspectDiagnostic().Status=="NON_OWNER_CLONE","CLONE_CLAIMED_ATTEMPT");
        }
        if(mode=="repeated_events") { for(int i=0;i<20;i++) { h.Step(State.DataLoaded);h.Step(State.Configure);h.Bar(); }Check(raw.Invokes==1 && raw.Disposes==0,"REPEATED_START"); }
        if(mode=="setdefaults_on_owner") { h.Step(State.SetDefaults);Check(h.ProbeEnabled,"OWNER_DEFAULTS_REARMED"); }
        if(mode!="inline")
        {
            if(mode=="async") { var thread=new Thread(raw.Fire);thread.Start();Check(thread.Join(30000),"ASYNC_TIMEOUT"); }
            else raw.Fire();
        }
        if(mode=="clone_after_seal") { string before=Contents(capture);var clone=h.Shallow();clone.Step(State.SetDefaults);clone.Step(State.Terminated);Check(before==Contents(capture),"CLONE_MODIFIED_SEAL"); }
        if(mode=="late_snapshot_throw")raw.Bars.ThrowTime=true;
        CheckSealed(h,capture,raw);
    }
    static void Failure(string folder,string mode)
    {
        Reset(mode);string capture=Path.Combine(folder,"capture");Directory.CreateDirectory(capture);var h=NewHost(capture,true);
        BarsRequest.AfterConstruct=()=>Settings(BarsRequest.Last,mode,h);
        if(mode=="closed")h.MarketReopenConfirmed=false;
        if(mode=="no_flow")h.NqDataFlowConfirmed=false;
        if(mode=="unstable")h.ConnectionStableConfirmed=false;
        if(mode=="blank_output")h.OutputDirectory="";
        if(mode=="null_output")h.OutputDirectory=null;
        if(mode=="missing_output")h.OutputDirectory=Path.Combine(folder,"missing");
        if(mode=="relative_output")h.OutputDirectory="relative-no-create";
        if(mode=="foreign_before_open")File.WriteAllText(Path.Combine(capture,"foreign.txt"),"KEEP");
        if(mode=="playback")NinjaTrader.Cbi.Connection.PlaybackConnection=new NinjaTrader.Cbi.Connection();
        if(mode=="timezone")NinjaTrader.Core.Globals.GeneralOptions.TimeZoneInfo=TradingHours.Next.TimeZoneInfo;
        if(mode=="chart_null")h.Bars=null;
        if(mode=="chart_instrument")h.Bars.Instrument.FullName="MNQ DEC26";
        if(mode=="chart_period")h.Bars.BarsPeriod.Value=2;
        if(mode=="chart_bid")h.Bars.BarsPeriod.MarketDataType=MarketDataType.Bid;
        if(mode=="chart_template")h.Bars.TradingHours.Name="OTHER";
        if(mode=="calendar_schedule")TradingHours.Next.Sessions[0].BeginTime=1800;
        if(mode=="calendar_holiday")TradingHours.Next.Holidays.Add(new DateTime(2026,9,14),Secret);
        if(mode=="request_constructor_error")BarsRequest.ThrowConstructor=true;
        if(mode=="request_configuration_error")BarsRequest.ThrowConfiguration=true;
        h.Step(State.Configure);h.Step(State.DataLoaded);var raw=BarsRequest.Last;
        if(mode=="terminate_pending")h.Step(State.Terminated);
        if(raw!=null && raw.Invokes==1 && mode!="inline_then_throw" && mode!="duplicate_inline" && mode!="submit_error")raw.Fire();
        var state=h.InspectDiagnostic();
        Check(state.Status=="FAILED_CLOSED" && !state.Sealed && !File.Exists(Seal(capture)),"FAILURE_NOT_BLOCKED:"+mode+":"+state.Status);
        if(raw!=null && !BarsRequest.ThrowConstructor)Check(raw.Disposes==1,"FAILURE_REQUEST_LEAK");
        if(raw!=null && raw.Bars!=null)Check(raw.Bars.Calls<=12 && raw.Bars.Creates<=11,"FAILURE_BUDGET");
        foreach(string f in Directory.GetFiles(capture,"*",SearchOption.AllDirectories))Check(!File.ReadAllText(f).Contains(Secret),"FAILURE_PRIVATE_TEXT_LEAK");
        Check(h.Output.Count==1 && !h.Output[0].Contains(Secret),"FAILURE_NOTIFICATION");
        string before=Contents(capture);int calls=raw==null || raw.Bars==null?0:raw.Bars.Calls,disposes=raw==null?0:raw.Disposes;
        if(raw!=null)raw.Fire();h.Step(State.DataLoaded);h.Step(State.Terminated);
        Check(before==Contents(capture) && (raw==null || raw.Disposes==disposes) && (raw==null || raw.Bars==null || raw.Bars.Calls==calls),"FAILURE_RETRIED");
        if(mode=="foreign_before_open")Check(File.ReadAllText(Path.Combine(capture,"foreign.txt"))=="KEEP","FOREIGN_FILE_MODIFIED");
    }
    static void Disabled(string folder,string mode)
    {
        Reset("normal");string capture=Path.Combine(folder,"capture");Directory.CreateDirectory(capture);var h=NewHost(capture,mode=="without_configure");
        if(mode=="ui_only") { h.Step(State.SetDefaults);h.Step(State.Terminated); }
        else if(mode=="terminated_before_load") { h.ProbeEnabled=true;h.Step(State.Terminated);h.Step(State.Configure);h.Step(State.DataLoaded); }
        else
        {
            if(mode!="without_configure")h.Step(State.Configure);
            h.Step(State.DataLoaded);
            if(mode=="enable_after_disabled") { h.ProbeEnabled=true;h.MarketReopenConfirmed=true;h.NqDataFlowConfirmed=true;h.ConnectionStableConfirmed=true;h.Step(State.Configure);h.Step(State.DataLoaded); }
            h.Bar();h.Step(State.Terminated);
        }
        Check(BarsRequest.TotalCreates==0 && Directory.GetFileSystemEntries(capture).Length==0 && h.Output.Count==0,"DISABLED_SIDE_EFFECT");
    }
    static void TwoHosts(string folder,bool same)
    {
        Reset("normal");string first=Path.Combine(folder,"capture");Directory.CreateDirectory(first);
        string second=same?first:Path.Combine(folder,"other-capture");if(!same)Directory.CreateDirectory(second);
        var a=NewHost(first,true);a.Step(State.Configure);a.Step(State.DataLoaded);var ar=BarsRequest.Last;
        string before=Contents(first);
        var b=NewHost(second,true);b.Step(State.Configure);b.Step(State.DataLoaded);var br=BarsRequest.Last;
        if(same)
        { Check(b.InspectDiagnostic().Status=="FAILED_CLOSED" && BarsRequest.TotalCreates==1 && ar.Disposes==0 && before==Contents(first),"SHARED_PATH_TOUCHED_OWNER"); }
        else
        { Check(BarsRequest.TotalCreates==2 && !Object.ReferenceEquals(ar,br),"NOT_INDEPENDENT");br.Fire();CheckSealed(b,second,br); }
        ar.Fire();CheckSealed(a,first,ar);
    }
    static void ConcurrentStop(string folder)
    {
        Reset("normal");string capture=Path.Combine(folder,"capture");Directory.CreateDirectory(capture);var h=NewHost(capture,true);
        using(var entered=new ManualResetEvent(false))using(var release=new ManualResetEvent(false))
        {
            BarsRequest.AfterConstruct=()=>BarsRequest.Last.AfterBars=()=>BarsRequest.Last.Bars.OnAdvance=()=> { entered.Set();Check(release.WaitOne(10000),"WAIT_TIMEOUT"); };
            h.Step(State.Configure);h.Step(State.DataLoaded);var raw=BarsRequest.Last;var thread=new Thread(raw.Fire);thread.IsBackground=true;thread.Start();
            try
            { Check(entered.WaitOne(10000),"NO_IN_FLIGHT_CALL");h.Step(State.Terminated);Check(raw.Disposes==0,"DISPOSED_ACTIVE_REQUEST"); }
            finally { release.Set(); }
            Check(thread.Join(30000),"STOP_JOIN_TIMEOUT");
            Check(raw.Disposes==1 && !h.InspectDiagnostic().Sealed && !File.Exists(Seal(capture)),"STOP_DID_NOT_FAIL_CLOSED");
        }
    }
    static readonly string[] Cases=new[] {
        "success_normal",
        "success_inline",
        "success_async",
        "success_all_false",
        "success_false",
        "success_constructor_error",
        "success_advance_error",
        "success_begin_error",
        "success_end_error",
        "success_bad_order",
        "success_bad_kind",
        "success_r0_false",
        "success_r0_constructor_error",
        "success_r0_advance_error",
        "success_r0_begin_error",
        "success_r0_end_error",
        "success_r0_bad_order",
        "success_r0_bad_kind",
        "success_mixed",
        "success_duplicate",
        "success_decreasing",
        "success_misaligned",
        "success_rows4503",
        "success_rows5520",
        "success_rows10002",
        "success_irrelevant_exceptions",
        "success_dispose_callback",
        "success_clone_active",
        "success_clone_setdefaults",
        "success_clone_after_seal",
        "success_repeated_events",
        "success_setdefaults_on_owner",
        "success_late_snapshot_throw",
        "failure_inline_then_throw",
        "failure_duplicate_inline",
        "failure_callback_error",
        "failure_wrong_callback",
        "failure_submit_error",
        "failure_snapshot_mutation",
        "failure_count_mutation",
        "failure_gettime_error",
        "failure_ohlc_error",
        "failure_wrong_returned_template",
        "failure_first_utc",
        "failure_duplicate_in_matrix",
        "failure_terminate_in_matrix",
        "failure_gate_in_matrix",
        "failure_output_in_matrix",
        "failure_chart_in_matrix",
        "failure_policy_in_matrix",
        "failure_playback_in_matrix",
        "failure_timezone_in_matrix",
        "failure_foreign_before_prepare",
        "failure_request_dispose_error",
        "failure_output_on_dispose",
        "failure_terminate_on_dispose",
        "failure_tamper_on_dispose",
        "failure_foreign_on_dispose",
        "failure_closed",
        "failure_no_flow",
        "failure_unstable",
        "failure_blank_output",
        "failure_null_output",
        "failure_missing_output",
        "failure_relative_output",
        "failure_foreign_before_open",
        "failure_playback",
        "failure_timezone",
        "failure_chart_null",
        "failure_chart_instrument",
        "failure_chart_period",
        "failure_chart_bid",
        "failure_chart_template",
        "failure_calendar_schedule",
        "failure_calendar_holiday",
        "failure_request_constructor_error",
        "failure_request_configuration_error",
        "failure_terminate_pending",
        "disabled_ui_only",
        "disabled_without_configure",
        "disabled_terminated_before_load",
        "disabled_defaults",
        "disabled_enable_after_disabled",
        "two_independent_hosts",
        "shared_capture_rejected",
        "terminate_concurrent_inflight"
    };
    static void Run(string root,string name)
    {
        string folder=Fresh(root,name);
        if(name.StartsWith("success_",StringComparison.Ordinal))Success(folder,name.Substring(8));
        else if(name.StartsWith("failure_",StringComparison.Ordinal))Failure(folder,name.Substring(8));
        else if(name.StartsWith("disabled_",StringComparison.Ordinal))Disabled(folder,name.Substring(9));
        else if(name=="two_independent_hosts")TwoHosts(folder,false);
        else if(name=="shared_capture_rejected")TwoHosts(folder,true);
        else if(name=="terminate_concurrent_inflight")ConcurrentStop(folder);
        else throw new Exception("UNKNOWN_TEST");
    }
    public static int Main(string[] args)
    {
        var results=new List<object>();int failed=0;
        try
        {
            if(args.Length==3 && args[0]=="--emit")
            {
                Success(args[1],args[2]);Console.WriteLine(new JavaScriptSerializer().Serialize(new {
                    classification="SYNTHETIC_NINJASCRIPT_HOST_ONLY",sealed_diagnostic=true,real_native_api_calls=0,
                    loaded_ninjatrader_assemblies=Array.FindAll(AppDomain.CurrentDomain.GetAssemblies(),a=>a.GetName().Name.StartsWith("NinjaTrader",StringComparison.Ordinal)).Length }));return 0;
            }
            if(args.Length!=2 || args[0]!="--all")throw new Exception("USE_ALL_OR_EMIT");
            foreach(string name in Cases)
            {
                try { Run(args[1],name);results.Add(new { name=name,status="PASS",detail="NONE" }); }
                catch(Exception e) { failed++;results.Add(new { name=name,status="FAIL",detail=e.GetType().Name+":"+e.Message }); }
            }
            Console.WriteLine(new JavaScriptSerializer().Serialize(new { classification="SYNTHETIC_NINJASCRIPT_HOST_ONLY",total=Cases.Length,
                passed=Cases.Length-failed,failed=failed,real_native_api_calls=0,
                loaded_ninjatrader_assemblies=Array.FindAll(AppDomain.CurrentDomain.GetAssemblies(),a=>a.GetName().Name.StartsWith("NinjaTrader",StringComparison.Ordinal)).Length,
                results=results }));return failed==0?0:1;
        }
        catch(Exception e) { Console.Error.WriteLine(e.GetType().Name+":"+e.Message);return 1; }
    }
}
