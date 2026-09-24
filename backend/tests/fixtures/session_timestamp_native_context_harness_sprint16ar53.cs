// Explicit SDK doubles for F and A/B/C/D/E integration. NEVER native evidence.
using System;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using System.Threading;
using System.Web.Script.Serialization;
using Arms.AI.Diagnostics.R53;
[assembly: AssemblyVersion("8.1.8.2")]
namespace NinjaTrader.Core
{
    public static class Globals { public static Options GeneralOptions=new Options(); }
    public sealed class Options { public TimeZoneInfo TimeZoneInfo=TimeZoneInfo.Utc; }
}
namespace NinjaTrader.Cbi
{
    public enum ErrorCode { NoError,Failed }
    public enum LookupPolicies { Repository,Provider }
    public enum MergePolicy { DoNotMerge,MergeBackAdjusted }
    public sealed class Connection { public static Connection PlaybackConnection; }
    public sealed class MasterInstrument { public string Name="NQ";public double TickSize=.25,PointValue=20; }
    public sealed class Instrument
    {
        public string FullName="NQ DEC26";public MasterInstrument MasterInstrument=new MasterInstrument();
        public DateTime Expiry=new DateTime(2026,12,1);
        public static Instrument Next=new Instrument();
        public static Instrument GetInstrument(string name) { ContextHarness.Check(name=="NQ DEC26","LOOKUP_NAME");return Next; }
    }
}
namespace NinjaTrader.Data
{
    using NinjaTrader.Cbi;
    public enum BarsPeriodType { Minute,Day }
    public enum MarketDataType { Last,Bid }
    public sealed class BarsPeriod { public BarsPeriodType BarsPeriodType;public int Value;public MarketDataType MarketDataType; }
    public sealed class Session { public DayOfWeek BeginDay,EndDay,TradingDay;public int BeginTime=1700,EndTime=1600; }
    public sealed class PartialHoliday { public bool IsEarlyEnd,IsLateBegin;public Session Constraint;public List<Session> Sessions=new List<Session>(); }
    public sealed class TradingHours
    {
        public string Name="CME US Index Futures ETH";public int Version=5119;
        public TimeZoneInfo TimeZoneInfo=TimeZoneInfo.FindSystemTimeZoneById("Central Standard Time");
        public List<Session> Sessions=new List<Session>();
        public Dictionary<DateTime,string> Holidays=new Dictionary<DateTime,string>();
        public Dictionary<DateTime,PartialHoliday> PartialHolidays=new Dictionary<DateTime,PartialHoliday>();
        public TradingHours() { for(int i=0;i<5;i++)Sessions.Add(new Session { BeginDay=(DayOfWeek)i,EndDay=(DayOfWeek)(i+1),TradingDay=(DayOfWeek)(i+1) }); }
        public static TradingHours Next=new TradingHours();
        public static TradingHours Get(string name) { ContextHarness.Check(name=="CME US Index Futures ETH","TEMPLATE_LOOKUP");return Next; }
    }
    public sealed class Bars
    {
        public Instrument Instrument;public BarsPeriod BarsPeriod;public TradingHours TradingHours;
        public int Count=5,TimeReads,Creates,Calls,Begins,Ends;
        public long ExtraTicks;public bool ChangedPrice,CountMutation,ThrowTime,ThrowOhlc,ReentrantTriggered;
        public string DataMode="normal",MatrixMode="normal";public Action OnAdvance,OnRead;
        public readonly List<DateTime> Queries=new List<DateTime>();public readonly List<int> Slots=new List<int>();
        public DateTime GetTime(int i)
        {
            TimeReads++;if(OnRead!=null && !ReentrantTriggered) { ReentrantTriggered=true;OnRead(); }
            if(ThrowTime && i==2)throw new InvalidOperationException(ContextHarness.Secret);
            if(CountMutation && i==2)Count++;
            DateTime t=new DateTime(2026,9,15,22,1,0,DateTimeKind.Unspecified).AddMinutes(i);
            if(DataMode=="first_utc" && i==0)t=DateTime.SpecifyKind(t,DateTimeKind.Utc);
            if(DataMode=="mixed" && i>=3)t=DateTime.SpecifyKind(t,DateTimeKind.Utc);
            if(DataMode=="duplicate" && i==2)t=t.AddMinutes(-1);
            if(DataMode=="decreasing" && i==2)t=t.AddMinutes(-3);
            if(DataMode=="misaligned" && i==2)t=t.AddTicks(1);
            if(DataMode=="reverse_end" && i==Count-1)t=t.AddDays(-3);
            if(i==2)t=t.AddTicks(ExtraTicks+(DataMode=="unstable" && TimeReads>Count?1:0));
            return t;
        }
        public double GetOpen(int i) { if(ThrowOhlc && i==2)throw new InvalidOperationException(ContextHarness.Secret);return ChangedPrice?20002:20000; }
        public double GetHigh(int i) { return 20003; }public double GetLow(int i) { return 19999; }
        public double GetClose(int i) { return 20000.25; }public long GetVolume(int i) { return 10; }
    }
    public sealed class SessionIterator
    {
        readonly Bars bars;readonly int slot;bool returned;
        public SessionIterator(Bars b)
        { bars=b;slot=++b.Creates;if(Hit("constructor_error"))throw new InvalidOperationException(ContextHarness.Secret); }
        bool Hit(string s) { return bars.MatrixMode==s && slot==1 || bars.MatrixMode=="r0_"+s && slot==10; }
        public bool GetNextSession(DateTime q,bool include)
        {
            ContextHarness.Check(include,"INCLUSION_CHANGED");bars.Calls++;bars.Queries.Add(q);bars.Slots.Add(slot);returned=false;
            if(bars.OnAdvance!=null)bars.OnAdvance();if(Hit("advance_error"))throw new InvalidOperationException(ContextHarness.Secret);
            returned=bars.MatrixMode!="all_false" && !Hit("false");return returned;
        }
        public DateTime ActualSessionBegin
        { get { bars.Begins++;ContextHarness.Check(returned,"READ_BEGIN_AFTER_FALSE");if(Hit("begin_error"))throw new InvalidOperationException(ContextHarness.Secret);return new DateTime(2026,9,13,22,0,0,DateTimeKind.Utc); } }
        public DateTime ActualSessionEnd
        { get { bars.Ends++;ContextHarness.Check(returned,"READ_END_AFTER_FALSE");if(Hit("end_error"))throw new InvalidOperationException(ContextHarness.Secret);
            if(Hit("bad_order"))return new DateTime(2026,9,13,21,0,0,DateTimeKind.Utc);
            return new DateTime(2026,9,14,21,0,0,Hit("bad_kind")?DateTimeKind.Unspecified:DateTimeKind.Utc); } }
    }
    public sealed class BarsRequest : IDisposable
    {
        public static BarsRequest Last;public static int TotalCreates;public static bool ThrowConstructor,ThrowConfiguration;
        public static Action AfterConstruct;public static string NextMode="normal";
        public readonly string Mode;public Instrument Instrument;private BarsPeriod period;
        public BarsPeriod BarsPeriod { get { return period; } set { if(ThrowConfiguration)throw new InvalidOperationException(ContextHarness.Secret);period=value; } }
        public TradingHours TradingHours;public LookupPolicies LookupPolicy;public MergePolicy MergePolicy;
        public DateTime FromLocal,ToLocal;public bool IsResetOnNewTradingDay,IsDividendAdjusted,IsSplitAdjusted;
        public Bars Bars;public int Invokes,Disposes;public Action OnDispose,AfterBars;
        private Action<BarsRequest,ErrorCode,string> callback;
        public BarsRequest(Instrument i,DateTime from,DateTime through)
        {
            TotalCreates++;Last=this;if(ThrowConstructor)throw new InvalidOperationException(ContextHarness.Secret);
            Instrument=i;FromLocal=from;ToLocal=through;Mode=NextMode;if(AfterConstruct!=null)AfterConstruct();
        }
        public void Request(Action<BarsRequest,ErrorCode,string> cb)
        {
            ContextHarness.Check(Disposes==0 && ++Invokes==1,"REQUEST_LIFETIME");callback=cb;
            ContextHarness.Check(LookupPolicy==LookupPolicies.Repository && MergePolicy==MergePolicy.DoNotMerge &&
                IsResetOnNewTradingDay && !IsDividendAdjusted && !IsSplitAdjusted &&
                FromLocal.Ticks==new DateTime(2026,9,16).Ticks && ToLocal.Ticks==new DateTime(2026,9,21).Ticks,"CONFIGURATION_NOT_APPLIED");
            Bars=new Bars { Instrument=Instrument,BarsPeriod=BarsPeriod,TradingHours=TradingHours,MatrixMode=Mode };
            if(AfterBars!=null)AfterBars();
            if(Mode=="inline" || Mode=="inline_then_throw" || Mode=="duplicate_inline")Fire();
            if(Mode=="duplicate_inline")Fire();
            if(Mode=="inline_then_throw" || Mode=="submit_error")throw new InvalidOperationException(ContextHarness.Secret);
        }
        public void Fire() { if(callback!=null)callback(Mode=="wrong_callback"?null:this,Mode=="callback_error"?ErrorCode.Failed:ErrorCode.NoError,ContextHarness.Secret); }
        public void Dispose() { Disposes++;if(OnDispose!=null)OnDispose(); }
    }
}
internal static class ContextHarness
{
    internal const string Secret="PRIVATE_PROVIDER_SENTINEL";
    static string gate="normal";static Action settingsHook;
    internal static void Check(bool ok,string id) { if(!ok)throw new Exception(id); }
    static void Reset(string mode)
    {
        gate="normal";settingsHook=null;NinjaTrader.Cbi.Instrument.Next=new NinjaTrader.Cbi.Instrument();
        NinjaTrader.Cbi.Connection.PlaybackConnection=null;NinjaTrader.Core.Globals.GeneralOptions=new NinjaTrader.Core.Options();
        NinjaTrader.Data.TradingHours.Next=new NinjaTrader.Data.TradingHours();NinjaTrader.Data.BarsRequest.Last=null;
        NinjaTrader.Data.BarsRequest.TotalCreates=0;NinjaTrader.Data.BarsRequest.ThrowConstructor=false;
        NinjaTrader.Data.BarsRequest.ThrowConfiguration=false;NinjaTrader.Data.BarsRequest.AfterConstruct=null;NinjaTrader.Data.BarsRequest.NextMode=mode;
    }
    static TimestampOperatorSettings Settings()
    {
        if(settingsHook!=null)settingsHook();if(gate=="null_settings")return null;
        return new TimestampOperatorSettings(gate!="disabled",gate!="closed",gate!="no_flow",gate!="unstable",gate=="terminated",gate=="output_changed"?"OTHER":"OUTPUT_TOKEN");
    }
    static T Clone<T>(T value) { return (T)typeof(object).GetMethod("MemberwiseClone",BindingFlags.Instance|BindingFlags.NonPublic).Invoke(value,null); }
    static void Reject(Action action,string guard)
    {
        bool rejected=false;try { action(); }catch(NativeContextGuardException e) { rejected=true;if(guard!=null)Check(e.GuardId==guard,"WRONG_GUARD:"+e.GuardId); }
        Check(rejected,"EXPECTED_CONTEXT_REJECTION");
    }
    static string Fresh(string root,string name)
    { string p=Path.Combine(root,name+"-"+Guid.NewGuid().ToString("N"));Directory.CreateDirectory(p);return p; }
    sealed class Unit
    {
        internal readonly object Owner=new object();internal readonly SessionTimestampNativeContextV1 Context;
        internal SessionTimestampNativeRequestV1 Wrapped;internal NinjaTrader.Data.BarsRequest Raw;
        internal Unit() { Context=new SessionTimestampNativeContextV1(Owner,Settings,"OUTPUT_TOKEN"); }
        internal void Create() { Wrapped=Context.CreateAndWrap(Owner);Raw=(NinjaTrader.Data.BarsRequest)Wrapped.Identity; }
        internal void Submit() { Wrapped.Submit((sender,ok)=>{}); }
        internal TimestampQueryPlan Bind() { return Context.Bind(Owner,Raw); }
        internal void Dispose() { if(Wrapped!=null)Wrapped.Dispose(); }
    }
    sealed class Attempt
    {
        internal readonly object Owner=new object();internal readonly SessionTimestampLifecycleV1 Life;
        internal readonly SessionTimestampNativeContextV1 Context;internal readonly string Folder,Mode;
        internal SessionTimestampNativeRequestV1 Wrapped;internal NinjaTrader.Data.BarsRequest Raw;
        internal SessionTimestampNativeCursorFactoryV1 Factory;internal SessionTimestampEvidenceV1 Writer;
        internal TimestampQueryPlan Plan;internal TimestampMatrixReport Report;internal string ContextText;
        internal Attempt(string folder,string mode) { Folder=folder;Mode=mode;Life=new SessionTimestampLifecycleV1(Owner);Context=new SessionTimestampNativeContextV1(Owner,Settings,"OUTPUT_TOKEN"); }
        internal void Start()
        {
            string capture=Path.Combine(Folder,"capture");Directory.CreateDirectory(capture);
            Life.Start(Owner,true,
                ()=> { Writer=new SessionTimestampEvidenceV1(Owner,Life,capture,Guid.NewGuid().ToString("D"),Guid.NewGuid().ToString("D"),"SYNTHETIC");return Writer; },
                ()=> {
                    Wrapped=Context.CreateAndWrap(Owner);Raw=(NinjaTrader.Data.BarsRequest)Wrapped.Identity;
                    Raw.AfterBars=()=> {
                        if(Mode=="mutation_during_matrix")Raw.Bars.OnAdvance=()=>Raw.Bars.ChangedPrice=true;
                        if(Mode=="policy_during_matrix")Raw.Bars.OnAdvance=()=>Raw.LookupPolicy=NinjaTrader.Cbi.LookupPolicies.Provider;
                        if(Mode=="duplicate_in_matrix")Raw.Bars.OnAdvance=()=>Raw.Fire();
                        if(Mode=="terminate_in_matrix")Raw.Bars.OnAdvance=()=>Life.Terminate(Owner);
                    };return Wrapped;
                },(r,checkpoint)=> {
                    Plan=Context.Bind(Owner,r.Identity);Factory=new SessionTimestampNativeCursorFactoryV1(Context.BoundBars(Owner),Plan,checkpoint,
                        (phase,c)=>Context.Check(Owner,phase,c));
                    Report=new SessionTimestampExecutorV1().Execute(Plan,Factory.Create,Factory.Check);Context.Revalidate(Owner);return Report;
                },report=> { Context.Revalidate(Owner);ContextText=Context.CapturedContext(Owner);Writer.Prepare(Owner,Plan,report); },
                phase=>Context.CheckLifecycle(Owner,phase));
        }
        internal void Complete()
        { Start();if(Raw!=null && Mode!="inline" && Mode!="inline_then_throw" && Mode!="duplicate_inline" && Mode!="submit_error")
            { if(Mode=="async") { var t=new Thread(Raw.Fire);t.Start();t.Join(); }else Raw.Fire(); } }
    }
    static void Success(string folder,string mode)
    {
        Reset(mode);var a=new Attempt(folder,mode);a.Complete();var s=a.Life.Inspect(a.Owner);
        Check(s.ReadyForSeal && a.Report.MatrixCompleted,"INTEGRATION_NOT_COMPLETE:"+s.StopGuard+":"+a.Context.FailureGuard);
        Check(a.Raw.Invokes==1 && a.Raw.Disposes==1 && a.Context.RequestConstructorAttempts==1 && a.Context.FactoryCleanupAttempts==0,"REQUEST_OWNERSHIP");
        Check(a.Raw.Bars.Creates==a.Report.ConstructorAttempts && a.Raw.Bars.Calls==a.Report.CallAttempts && a.Raw.Bars.Begins==a.Report.BeginReadAttempts &&
            a.Raw.Bars.Ends==a.Report.EndReadAttempts && a.Raw.Bars.Creates<=11 && a.Raw.Bars.Calls<=12,"INTEGRATION_COUNTERS");
        Check(a.Plan.RawFirst.Kind==DateTimeKind.Unspecified && a.Plan.ReturnedRows==5 && a.Plan.Cases[0].SourceIndex==0,"SOURCE_BINDING");
        Check(!a.ContextText.Contains(Secret),"CONTEXT_SECRET_LEAK");a.Writer.PublishSeal(a.Owner);Check(a.Writer.Sealed,"NO_SEAL");
        // Context test artifact is a SIBLING of D's capture. It is not yet bound to D's seal.
        File.WriteAllText(Path.Combine(folder,"context.json"),a.ContextText,new System.Text.UTF8Encoding(false));
        a.Context.Invalidate(a.Owner);Check(a.Context.CapturedContext(a.Owner)==a.ContextText,"CACHED_CONTEXT_CHANGED");
        a.Raw.Fire();a.Wrapped.Dispose();Check(a.Raw.Disposes==1,"DUPLICATE_DISPOSAL");
    }
    static void Failure(string folder,string mode)
    {
        Reset(mode);var a=new Attempt(folder,mode);a.Complete();var state=a.Life.Inspect(a.Owner);
        Check(!state.ReadyForSeal && state.Status=="FAILED_CLOSED","INTEGRATION_FAILURE_NOT_BLOCKED");
        Check(!File.Exists(Path.Combine(folder,"capture",SessionTimestampEvidenceV1.SealName)),"FAILURE_SEAL");
        Check(a.Raw==null || a.Raw.Disposes==1,"FAILED_REQUEST_LEAK");
        Check(a.Raw==null || a.Raw.Bars==null || a.Raw.Bars.Calls<=12,"BUDGET_ON_FAILURE");
    }
    static void MainCase(string root,string name)
    {
        if(name.StartsWith("success_",StringComparison.Ordinal)) { Success(Fresh(root,name),name.Substring(8));return; }
        if(name.StartsWith("failure_",StringComparison.Ordinal)) { Failure(Fresh(root,name),name.Substring(8));return; }
        Reset("normal");var u=new Unit();
        if(name.StartsWith("gate_",StringComparison.Ordinal))
        {
            gate=name.Substring(5);Reject(u.Create,"OPERATOR_GATES_CHANGED");Check(NinjaTrader.Data.BarsRequest.TotalCreates==0,"GATE_CREATED_REQUEST");return;
        }
        if(name=="timezone" || name=="utc_id_wrong_rules" || name=="playback")
        {
            if(name=="timezone")NinjaTrader.Core.Globals.GeneralOptions.TimeZoneInfo=TimeZoneInfo.FindSystemTimeZoneById("Central Standard Time");
            if(name=="utc_id_wrong_rules")NinjaTrader.Core.Globals.GeneralOptions.TimeZoneInfo=TimeZoneInfo.CreateCustomTimeZone("UTC",TimeSpan.FromHours(1),"bad","bad");
            if(name=="playback")NinjaTrader.Cbi.Connection.PlaybackConnection=new NinjaTrader.Cbi.Connection();
            Reject(u.Create,name=="playback"?"PLAYBACK_CONNECTED":"APPLICATION_ZONE_NOT_UTC");Check(NinjaTrader.Data.BarsRequest.TotalCreates==0,"ENV_CREATED_REQUEST");return;
        }
        if(name.StartsWith("instrument_",StringComparison.Ordinal))
        {
            var i=NinjaTrader.Cbi.Instrument.Next;
            if(name=="instrument_null")NinjaTrader.Cbi.Instrument.Next=null;
            if(name=="instrument_name")i.FullName="OTHER";
            if(name=="instrument_master")i.MasterInstrument.Name="MNQ";
            if(name=="instrument_expiry")i.Expiry=new DateTime(2026,9,1);
            if(name=="instrument_tick")i.MasterInstrument.TickSize=.5;
            if(name=="instrument_point")i.MasterInstrument.PointValue=2;
            Reject(u.Create,"INSTRUMENT_MISMATCH");Check(NinjaTrader.Data.BarsRequest.TotalCreates==0,"INSTRUMENT_CREATED_REQUEST");return;
        }
        if(name.StartsWith("calendar_",StringComparison.Ordinal))
        {
            var th=NinjaTrader.Data.TradingHours.Next;
            if(name=="calendar_name")th.Name="OTHER";
            if(name=="calendar_zone")th.TimeZoneInfo=TimeZoneInfo.Utc;
            if(name=="calendar_rules")th.TimeZoneInfo=TimeZoneInfo.CreateCustomTimeZone("Central Standard Time",TimeSpan.FromHours(-6),"bad","bad");
            if(name=="calendar_sessions")th.Sessions.RemoveAt(0);
            if(name=="calendar_schedule")th.Sessions[0].BeginTime=1800;
            if(name=="calendar_full_holiday")th.Holidays.Add(new DateTime(2026,9,14),Secret);
            if(name=="calendar_partial_holiday")th.PartialHolidays.Add(new DateTime(2026,9,15),new NinjaTrader.Data.PartialHoliday());
            if(name=="calendar_holiday_budget")for(int j=0;j<4097;j++)th.Holidays.Add(new DateTime(1980,1,1).AddDays(j),Secret);
            if(name=="calendar_partial_budget") { var ph=new NinjaTrader.Data.PartialHoliday();for(int j=0;j<33;j++)ph.Sessions.Add(th.Sessions[0]);th.PartialHolidays.Add(new DateTime(2025,1,1),ph); }
            Reject(u.Create,null);Check(NinjaTrader.Data.BarsRequest.TotalCreates==0,"BAD_CALENDAR_CREATED_REQUEST");return;
        }
        if(name=="constructor_error_cleanup" || name=="configure_error_cleanup" || name=="environment_during_create")
        {
            NinjaTrader.Data.BarsRequest.ThrowConstructor=name=="constructor_error_cleanup";
            NinjaTrader.Data.BarsRequest.ThrowConfiguration=name=="configure_error_cleanup";
            if(name=="environment_during_create")NinjaTrader.Data.BarsRequest.AfterConstruct=()=>gate="closed";
            Reject(u.Create,null);Check(u.Context.RequestConstructorAttempts==1,"CONSTRUCTOR_ATTEMPTS");
            Check(u.Context.FactoryCleanupAttempts==(name=="constructor_error_cleanup"?0:1),"FACTORY_CLEANUP_COUNTER");
            Check(NinjaTrader.Data.BarsRequest.Last.Disposes==(name=="constructor_error_cleanup"?0:1),"FACTORY_CLEANUP_DISPOSE");return;
        }
        if(name=="clone_preserves_owner" || name=="wrong_owner")
        {
            var clone=Clone(u.Context);
            if(name=="clone_preserves_owner") { Reject(()=>clone.CreateAndWrap(u.Owner),"CONTEXT_NOT_OWNER");Reject(()=>clone.Invalidate(u.Owner),"CONTEXT_NOT_OWNER"); }
            else Reject(()=>u.Context.CreateAndWrap(new object()),"CONTEXT_NOT_OWNER");
            u.Create();u.Submit();u.Bind();Check(!u.Context.Failed && NinjaTrader.Data.BarsRequest.TotalCreates==1,"OWNER_POISONED");u.Dispose();return;
        }
        if(name=="reentrant_environment")
        {
            bool once=false;settingsHook=()=>{if(!once) { once=true;Reject(()=>u.Context.CheckEnvironment(u.Owner),"CONTEXT_REENTRANT"); }};
            Reject(u.Create,null);Check(u.Context.Failed && NinjaTrader.Data.BarsRequest.TotalCreates<=1,"REENTRANT_NOT_LATCHED");return;
        }
        if(name=="irrelevant_holidays_recorded")
        {
            var th=NinjaTrader.Data.TradingHours.Next;th.Holidays.Add(new DateTime(2025,1,1),Secret);
            var ph=new NinjaTrader.Data.PartialHoliday { IsEarlyEnd=true,Constraint=th.Sessions[0] };ph.Sessions.Add(th.Sessions[1]);
            th.PartialHolidays.Add(new DateTime(2025,2,1),ph);u.Create();u.Submit();u.Bind();
            string json=u.Context.CapturedContext(u.Owner);Check(json.Contains("early") && !json.Contains(Secret),"HOLIDAY_REDACTION");u.Dispose();return;
        }
        u.Create();
        if(name=="factory_repeated") { Reject(u.Create,"REQUEST_FACTORY_ALREADY_USED");Check(NinjaTrader.Data.BarsRequest.TotalCreates==1 && u.Raw.Disposes==0,"FACTORY_REUSE");u.Dispose();return; }
        if(name.StartsWith("request_mutate_",StringComparison.Ordinal))
        {
            string change=name.Substring(15);
            if(change=="lookup")u.Raw.LookupPolicy=NinjaTrader.Cbi.LookupPolicies.Provider;
            if(change=="merge")u.Raw.MergePolicy=NinjaTrader.Cbi.MergePolicy.MergeBackAdjusted;
            if(change=="reset")u.Raw.IsResetOnNewTradingDay=false;
            if(change=="dividend")u.Raw.IsDividendAdjusted=true;
            if(change=="split")u.Raw.IsSplitAdjusted=true;
            if(change=="from")u.Raw.FromLocal=u.Raw.FromLocal.AddDays(1);
            if(change=="through")u.Raw.ToLocal=u.Raw.ToLocal.AddDays(1);
            if(change=="kind")u.Raw.FromLocal=DateTime.SpecifyKind(u.Raw.FromLocal,DateTimeKind.Utc);
            if(change=="period")u.Raw.BarsPeriod.Value=2;
            if(change=="calendar_object")u.Raw.TradingHours=new NinjaTrader.Data.TradingHours();
            if(change=="calendar_content")u.Raw.TradingHours.Version++;
            Reject(u.Submit,null);Check(u.Raw.Invokes==0,"MUTATED_REQUEST_SUBMITTED");u.Dispose();return;
        }
        u.Submit();var b=u.Raw.Bars;
        if(name=="foreign_callback" || name=="null_callback")
        { Reject(()=>u.Context.Bind(u.Owner,name=="foreign_callback"?new object():null),"CALLBACK_REQUEST_IDENTITY_MISMATCH");u.Dispose();return; }
        // F1: bind_repeated is a successful first bind followed by a rejected second bind.
        // It must NOT enter the invalid-first-bind fault-injection branch.
        if(name.StartsWith("bind_",StringComparison.Ordinal) && name!="bind_repeated")
        {
            string mode=name.Substring(5);
            if(mode=="count_low")b.Count=2;if(mode=="count_high")b.Count=10003;
            if(mode=="first_utc" || mode=="reverse_end" || mode=="unstable")b.DataMode=mode;
            if(mode=="gettime")b.ThrowTime=true;if(mode=="ohlc")b.ThrowOhlc=true;if(mode=="count_mutation")b.CountMutation=true;
            if(mode=="bars_period")b.BarsPeriod=new NinjaTrader.Data.BarsPeriod { Value=2 };
            if(mode=="bars_calendar")b.TradingHours=new NinjaTrader.Data.TradingHours { Version=5120 };
            Reject(()=>u.Bind(),null);Check(b.Creates==0 && b.Calls==0,"BIND_CALLED_ITERATOR");
            if(mode=="gettime" || mode=="ohlc")Check(u.Context.FailureSourceIndex==2,"FAILURE_INDEX_LOST");u.Dispose();return;
        }
        if(name=="count_4503")b.Count=4503;if(name=="count_5520")b.Count=5520;if(name=="count_max")b.Count=10002;
        if(name=="mixed_kinds")b.DataMode="mixed";
        if(name=="observe_duplicate")b.DataMode="duplicate";if(name=="observe_decreasing")b.DataMode="decreasing";if(name=="observe_misaligned")b.DataMode="misaligned";
        if(name=="separate_returned_calendar")b.TradingHours=new NinjaTrader.Data.TradingHours();
        var plan=u.Bind();
        if(name.StartsWith("mutate_",StringComparison.Ordinal))
        {
            if(name=="mutate_price")b.ChangedPrice=true;
            if(name=="mutate_timestamp")b.ExtraTicks=1;
            if(name=="mutate_count")b.Count++;
            if(name=="mutate_kind")b.DataMode="mixed";
            if(name=="mutate_bars_object")u.Raw.Bars=new NinjaTrader.Data.Bars { Instrument=b.Instrument,BarsPeriod=b.BarsPeriod,TradingHours=b.TradingHours };
            if(name=="mutate_template_version")b.TradingHours.Version++;
            if(name=="mutate_template_object")b.TradingHours=new NinjaTrader.Data.TradingHours();
            if(name=="mutate_environment")gate="closed";
            Reject(()=>u.Context.Revalidate(u.Owner),null);b.ChangedPrice=false;b.ExtraTicks=0;
            Reject(()=>u.Context.Revalidate(u.Owner),"CONTEXT_NOT_USABLE");Check(b.Calls==0,"MUTATION_CALLED_NATIVE");u.Dispose();return;
        }
        if(name=="bind_repeated")
        {
            Check(plan!=null && !u.Context.Failed,"FIRST_BIND_DID_NOT_SUCCEED");
            int scans=u.Context.FullScanAttempts,reads=b.TimeReads;
            string saved=u.Context.CapturedContext(u.Owner);
            Reject(()=>u.Bind(),"SNAPSHOT_ALREADY_BOUND");
            Check(u.Context.Failed && u.Context.FailureGuard=="SNAPSHOT_ALREADY_BOUND","REPEAT_BIND_NOT_LATCHED");
            Check(u.Context.FullScanAttempts==scans && b.TimeReads==reads,"REPEAT_BIND_RESCANNED");
            Check(NinjaTrader.Data.BarsRequest.TotalCreates==1 && u.Raw.Invokes==1 &&
                u.Context.RequestConstructorAttempts==1,"REPEAT_BIND_CREATED_OR_SUBMITTED_REQUEST");
            Check(u.Raw.Disposes==0 && u.Context.FactoryCleanupAttempts==0,"REPEAT_BIND_CLOSED_OWNER_REQUEST");
            Check(u.Context.CapturedContext(u.Owner)==saved,"REPEAT_BIND_CHANGED_CAPTURED_CONTEXT");
            Reject(()=>u.Context.Revalidate(u.Owner),"CONTEXT_NOT_USABLE");
            Check(u.Context.FullScanAttempts==scans && b.TimeReads==reads,"FAILED_CONTEXT_RESCANNED");
            Check(b.Creates==0 && b.Calls==0 && b.Begins==0 && b.Ends==0,"REPEAT_BIND_CALLED_ITERATOR");
            u.Dispose();Check(u.Raw.Disposes==1 && u.Context.FactoryCleanupAttempts==0,"REPEAT_BIND_OWNER_CLEANUP");
            return;
        }
        if(name=="invalidation") { u.Context.Invalidate(u.Owner);Reject(()=>u.Context.Revalidate(u.Owner),"CONTEXT_NOT_USABLE");Check(u.Raw.Disposes==0,"INVALIDATE_DISPOSED_OTHER_OWNER");u.Dispose();return; }
        if(name=="foreign_plan_control")
        { var p=SessionTimestampPlanV1.Build(plan.RawFirst,plan.RawLast,plan.ReturnedRows,plan.SnapshotSha256,plan.TemplateSha256,b.TradingHours.TimeZoneInfo);
          Reject(()=>u.Context.Check(u.Owner,"BEFORE_CASE",p.Cases[0]),"CONTROL_NOT_IN_BOUND_PLAN");u.Dispose();return; }
        u.Context.Revalidate(u.Owner);Check(plan.ReturnedRows==b.Count && plan.Cases.Count==12 && plan.Cases[0].Time.Raw.Ticks==b.GetTime(0).Ticks,"BOUND_PLAN_INVALID");
        string context=u.Context.CapturedContext(u.Owner);Check(context.Contains("RAW_TICKS_AND_KIND_NOT_NORMALIZED") && !context.Contains(Secret),"CONTEXT_PAYLOAD");
        var envelope=new JavaScriptSerializer().Deserialize<Dictionary<string,object>>(context);
        var measured=(Dictionary<string,object>)envelope["snapshot"];
        Check(Convert.ToInt32(measured["rows"])==b.Count,"SUMMARY_ROW_COUNT");
        if(name=="mixed_kinds")Check(Convert.ToInt32(measured["unspecified_count"])==3 && Convert.ToInt32(measured["utc_count"])==2 &&
            Convert.ToInt32(measured["kind_transitions"])==1,"MIXED_KINDS_NOT_OBSERVED");
        if(name=="observe_duplicate")Check(Convert.ToInt32(measured["duplicate_pairs"])==1,"DUPLICATE_NOT_OBSERVED");
        if(name=="observe_decreasing")Check(Convert.ToInt32(measured["decreasing_pairs"])==1,"DECREASE_NOT_OBSERVED");
        if(name=="observe_misaligned")Check(Convert.ToInt32(measured["misaligned_count"])==1,"MISALIGNMENT_NOT_OBSERVED");
        Check(b.Creates==0 && b.Calls==0 && u.Context.FullScanAttempts>=3,"CONTEXT_NATIVE_SURFACE");
        u.Dispose();Check(u.Raw.Disposes==1 && u.Context.FactoryCleanupAttempts==0,"EXCLUSIVE_REQUEST_OWNERSHIP");
    }
    internal static string[] Cases={ "success_normal",
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
        "failure_inline_then_throw",
        "failure_duplicate_inline",
        "failure_callback_error",
        "failure_wrong_callback",
        "failure_submit_error",
        "failure_mutation_during_matrix",
        "failure_policy_during_matrix",
        "failure_duplicate_in_matrix",
        "failure_terminate_in_matrix",
        "gate_disabled",
        "gate_closed",
        "gate_no_flow",
        "gate_unstable",
        "gate_terminated",
        "gate_output_changed",
        "gate_null_settings",
        "timezone",
        "utc_id_wrong_rules",
        "playback",
        "instrument_null",
        "instrument_name",
        "instrument_master",
        "instrument_expiry",
        "instrument_tick",
        "instrument_point",
        "calendar_name",
        "calendar_zone",
        "calendar_rules",
        "calendar_sessions",
        "calendar_schedule",
        "calendar_full_holiday",
        "calendar_partial_holiday",
        "calendar_holiday_budget",
        "calendar_partial_budget",
        "constructor_error_cleanup",
        "configure_error_cleanup",
        "environment_during_create",
        "clone_preserves_owner",
        "wrong_owner",
        "reentrant_environment",
        "irrelevant_holidays_recorded",
        "factory_repeated",
        "request_mutate_lookup",
        "request_mutate_merge",
        "request_mutate_reset",
        "request_mutate_dividend",
        "request_mutate_split",
        "request_mutate_from",
        "request_mutate_through",
        "request_mutate_kind",
        "request_mutate_period",
        "request_mutate_calendar_object",
        "request_mutate_calendar_content",
        "foreign_callback",
        "null_callback",
        "bind_count_low",
        "bind_count_high",
        "bind_first_utc",
        "bind_reverse_end",
        "bind_unstable",
        "bind_gettime",
        "bind_ohlc",
        "bind_count_mutation",
        "bind_bars_period",
        "bind_bars_calendar",
        "count_4503",
        "count_5520",
        "count_max",
        "mixed_kinds",
        "observe_duplicate",
        "observe_decreasing",
        "observe_misaligned",
        "separate_returned_calendar",
        "mutate_price",
        "mutate_timestamp",
        "mutate_count",
        "mutate_kind",
        "mutate_bars_object",
        "mutate_template_version",
        "mutate_template_object",
        "mutate_environment",
        "bind_repeated",
        "invalidation",
        "foreign_plan_control",
        "bound_context_normal" };
    public static int Main(string[] args)
    {
        if(args.Length==3 && args[0]=="--emit")
        { Check(Array.IndexOf(Cases,"success_"+args[2])>=0,"UNKNOWN_SAMPLE");Success(args[1],args[2]);Console.WriteLine("{\"classification\":\"SYNTHETIC_LOADED_CONTEXT_ONLY\",\"sealed\":true}");return 0; }
        if(args.Length<2)return 2;int pass=0,fail=0;var results=new List<object>();
        foreach(string name in Cases)
        {
            if(args[0]!="--all" && !(args[0]=="--case" && args.Length==3 && name==args[2]))continue;
            try { MainCase(args[1],name);results.Add(new { name=name,status="PASS",detail="NONE" });pass++; }
            catch(Exception e) { results.Add(new { name=name,status="FAIL",detail=e.GetType().Name+":"+e.Message });fail++; }
        }
        Console.WriteLine(new JavaScriptSerializer().Serialize(new { classification="SYNTHETIC_LOADED_CONTEXT_ONLY",total=pass+fail,passed=pass,failed=fail,
            real_native_api_calls=0,loaded_ninjatrader_assemblies=Array.FindAll(AppDomain.CurrentDomain.GetAssemblies(),x=>x.GetName().Name.StartsWith("NinjaTrader",StringComparison.Ordinal)).Length,results=results }));
        return fail==0 && pass>0?0:1;
    }
}
