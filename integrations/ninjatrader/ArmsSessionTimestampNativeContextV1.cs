// R5.3-F: explicit request configuration + loaded snapshot/calendar validation.
// NOT an Indicator. No automatic request submission, iterators, files or orders.
// Future host must compose C/D/E, bind persisted context and authorize one run.
using System;
using System.Collections.Generic;
using System.Globalization;
using System.Security.Cryptography;
using System.Text;
using System.Threading;
using System.Web.Script.Serialization;
using NinjaTrader.Cbi;
using NinjaTrader.Data;

namespace Arms.AI.Diagnostics.R53
{
    internal sealed class NativeContextGuardException : InvalidOperationException
    {
        public string GuardId { get; private set; }
        internal NativeContextGuardException(string id) : base(id) { GuardId=id; }
    }
    internal sealed class TimestampOperatorSettings
    {
        internal bool Enabled { get; private set; }
        internal bool MarketOpen { get; private set; }
        internal bool DataFlow { get; private set; }
        internal bool StableConnection { get; private set; }
        internal bool Terminated { get; private set; }
        internal string OutputDirectory { get; private set; }
        internal TimestampOperatorSettings(bool enabled,bool market,bool flow,bool stable,bool terminated,string output)
        { Enabled=enabled;MarketOpen=market;DataFlow=flow;StableConnection=stable;Terminated=terminated;OutputDirectory=output; }
    }
    internal sealed class SessionTimestampNativeContextV1
    {
        internal const string Version="R5.3-F/native-context/1";
        internal const string TemplateName="CME US Index Futures ETH";
        internal const string ZoneId="Central Standard Time";
        internal const int MaximumRows=10002,MaximumCalendarItems=4096,MaximumCalendarBytes=65536,MaximumContextBytes=131072;
        private static readonly DateTime FromDate=new DateTime(2026,9,16),ThroughDate=new DateTime(2026,9,21);
        private readonly SessionTimestampNativeContextV1 instanceOwner;
        private readonly object hostOwner;
        private readonly Func<TimestampOperatorSettings> readSettings;
        private readonly string output;
        private BarsRequest request;
        private Bars selectedBars;
        private TradingHours requestedCalendar,returnedCalendar;
        private TimestampQueryPlan plan;
        private Measurement snapshot;
        private string configuration,calendar,contextJson;
        private int busy,failed,invalidated,creates,cleanup,fullScans;
        private bool bound;
        private string operation="NOT_STARTED",failureGuard="NONE",failureType="NONE";
        private int sourceIndex=-1;

        internal SessionTimestampNativeContextV1(object owner,Func<TimestampOperatorSettings> settings,string outputDirectory)
        {
            Require(owner!=null && settings!=null && !String.IsNullOrWhiteSpace(outputDirectory),"CONTEXT_DEPENDENCY_MISSING");
            instanceOwner=this;hostOwner=owner;readSettings=settings;output=outputDirectory;
        }
        private static int Read(ref int value) { return Interlocked.CompareExchange(ref value,0,0); }
        private static void Require(bool ok,string guard) { if(!ok)throw new NativeContextGuardException(guard); }
        private void Owner(object owner)
        { Require(Object.ReferenceEquals(this,instanceOwner) && Object.ReferenceEquals(owner,hostOwner),"CONTEXT_NOT_OWNER"); }
        private T Run<T>(object owner,Func<T> action)
        {
            Owner(owner);
            Require(Read(ref failed)==0 && Read(ref invalidated)==0,"CONTEXT_NOT_USABLE");
            if(Interlocked.CompareExchange(ref busy,1,0)!=0)
            { Interlocked.Exchange(ref failed,1);throw new NativeContextGuardException("CONTEXT_REENTRANT"); }
            try
            {
                T result=action();
                Require(Read(ref failed)==0 && Read(ref invalidated)==0,"CONTEXT_CHANGED_DURING_OPERATION");
                return result;
            }
            catch(Exception error)
            {
                Interlocked.Exchange(ref failed,1);
                if(failureGuard=="NONE")
                {
                    var known=error as NativeContextGuardException;
                    var planned=error as PlanGuardException;
                    failureGuard=known!=null?known.GuardId:planned!=null?planned.GuardId:"CONTEXT_OPERATION_FAILED";
                    failureType=error is InvalidOperationException?"InvalidOperationException":error is ArgumentException?"ArgumentException":"OTHER";
                }
                throw new NativeContextGuardException(failureGuard);
            }
            finally { Interlocked.Exchange(ref busy,0); }
        }
        internal int RequestConstructorAttempts { get { Owner(hostOwner);return creates; } }
        internal int FactoryCleanupAttempts { get { Owner(hostOwner);return cleanup; } }
        internal int FullScanAttempts { get { Owner(hostOwner);return fullScans; } }
        internal object RequestIdentity { get { Owner(hostOwner);return request; } }
        internal bool Failed { get { Owner(hostOwner);return Read(ref failed)!=0; } }
        internal string FailureGuard { get { Owner(hostOwner);return failureGuard; } }
        internal string FailureType { get { Owner(hostOwner);return failureType; } }
        internal string FailureOperation { get { Owner(hostOwner);return operation; } }
        internal int FailureSourceIndex { get { Owner(hostOwner);return sourceIndex; } }
        internal void Invalidate(object owner)
        {
            // No resource is closed here. C/E own the transferred request lifetime.
            Owner(owner);Interlocked.Exchange(ref invalidated,1);
        }
        private void Environment()
        {
            operation="OPERATOR_ENVIRONMENT";sourceIndex=-1;
            var settings=readSettings();
            Require(settings!=null && settings.Enabled && settings.MarketOpen && settings.DataFlow &&
                settings.StableConnection && !settings.Terminated && settings.OutputDirectory==output,"OPERATOR_GATES_CHANGED");
            Require(typeof(BarsRequest).Assembly.GetName().Version.ToString()=="8.1.8.2","SDK_VERSION_MISMATCH");
            var options=NinjaTrader.Core.Globals.GeneralOptions;
            Require(options!=null && options.TimeZoneInfo!=null && options.TimeZoneInfo.Id=="UTC" &&
                options.TimeZoneInfo.HasSameRules(TimeZoneInfo.Utc),"APPLICATION_ZONE_NOT_UTC");
            Require(Connection.PlaybackConnection==null,"PLAYBACK_CONNECTED");
        }
        internal void CheckEnvironment(object owner)
        { Run(owner,()=> { Environment();return true; }); }
        private static void InstrumentContract(Instrument i)
        {
            Require(i!=null && i.MasterInstrument!=null && i.FullName=="NQ DEC26" && i.MasterInstrument.Name=="NQ" &&
                i.Expiry.Year==2026 && i.Expiry.Month==12 && i.MasterInstrument.TickSize==.25 &&
                i.MasterInstrument.PointValue==20,"INSTRUMENT_MISMATCH");
        }
        private static void PeriodContract(BarsPeriod p)
        { Require(p!=null && p.BarsPeriodType==BarsPeriodType.Minute && p.Value==1 && p.MarketDataType==MarketDataType.Last,"PERIOD_MISMATCH"); }
        private static string Hex(byte[] bytes)
        { return BitConverter.ToString(bytes).Replace("-","").ToLowerInvariant(); }
        private static string Hash(string text)
        { using(var h=SHA256.Create())return Hex(h.ComputeHash(new UTF8Encoding(false,true).GetBytes(text))); }
        private static string Json(object value)
        { return new JavaScriptSerializer { MaxJsonLength=MaximumContextBytes }.Serialize(value); }
        private static object Stamp(DateTime t)
        { return new { clock=t.ToString("yyyy-MM-ddTHH:mm:ss.fffffff",CultureInfo.InvariantCulture),ticks=t.Ticks,kind=t.Kind.ToString() }; }
        private static bool Same(DateTime a,DateTime b) { return a.Ticks==b.Ticks && a.Kind==b.Kind; }
        private static string SessionText(Session s)
        {
            Require(s!=null,"SESSION_NULL");
            return String.Join("|",new[] { ((int)s.BeginDay).ToString(CultureInfo.InvariantCulture),s.BeginTime.ToString(CultureInfo.InvariantCulture),
                ((int)s.EndDay).ToString(CultureInfo.InvariantCulture),s.EndTime.ToString(CultureInfo.InvariantCulture),((int)s.TradingDay).ToString(CultureInfo.InvariantCulture) });
        }
        private static bool Relevant(DateTime date)
        { return date.Date>=new DateTime(2026,9,13) && date.Date<=new DateTime(2026,9,22); }
        private static object Calendar(TradingHours th)
        {
            Require(th!=null && th.Name==TemplateName && th.TimeZoneInfo!=null && th.TimeZoneInfo.Id==ZoneId,"TEMPLATE_IDENTITY_MISMATCH");
            Require(th.Sessions!=null && th.Sessions.Count==5,"TEMPLATE_SESSION_COUNT");
            var sessions=new List<string>();
            foreach(var s in th.Sessions)sessions.Add(SessionText(s));
            sessions.Sort(StringComparer.Ordinal);
            for(int i=0;i<5;i++)Require(sessions[i]==i+"|1700|"+(i+1)+"|1600|"+(i+1),"TEMPLATE_WEEKLY_SCHEDULE_MISMATCH");
            Require(th.Holidays!=null && th.PartialHolidays!=null && th.Holidays.Count<=MaximumCalendarItems &&
                th.PartialHolidays.Count<=MaximumCalendarItems,"CALENDAR_ITEM_LIMIT");
            var holidays=new List<string>();var partials=new List<string>();
            foreach(var h in th.Holidays)
            {
                Require(!Relevant(h.Key),"RELEVANT_FULL_HOLIDAY");
                // Descriptions are not calendar rules and can contain private text; do not persist them.
                holidays.Add(h.Key.Ticks.ToString(CultureInfo.InvariantCulture)+"|"+h.Key.Kind.ToString());
            }
            foreach(var h in th.PartialHolidays)
            {
                Require(!Relevant(h.Key),"RELEVANT_PARTIAL_HOLIDAY");
                var p=h.Value;Require(p!=null,"PARTIAL_HOLIDAY_NULL");
                var definitions=new List<string>();
                if(p.Sessions!=null)
                {
                    Require(p.Sessions.Count<=32,"PARTIAL_SESSION_LIMIT");
                    foreach(var s in p.Sessions)definitions.Add(SessionText(s));
                }
                partials.Add(Json(new { ticks=h.Key.Ticks,kind=h.Key.Kind.ToString(),early=p.IsEarlyEnd,late=p.IsLateBegin,
                    constraint=p.Constraint==null?null:SessionText(p.Constraint),sessions=definitions }));
            }
            holidays.Sort(StringComparer.Ordinal);partials.Sort(StringComparer.Ordinal);
            string zone=th.TimeZoneInfo.ToSerializedString();
            Require(Encoding.UTF8.GetByteCount(zone)<=32768,"ZONE_RULES_LIMIT");
            // Explicit loaded-zone conversions of REFERENCE wall clocks, never bar normalization.
            DateTime[] walls={new DateTime(2026,9,13,17,0,0),new DateTime(2026,9,14,16,0,0),
                new DateTime(2026,9,14,17,0,0),new DateTime(2026,9,15,16,0,0)};
            DateTime[] expected={new DateTime(2026,9,13,22,0,0,DateTimeKind.Utc),new DateTime(2026,9,14,21,0,0,DateTimeKind.Utc),
                new DateTime(2026,9,14,22,0,0,DateTimeKind.Utc),new DateTime(2026,9,15,21,0,0,DateTimeKind.Utc)};
            var references=new List<object>();
            for(int i=0;i<walls.Length;i++)
            {
                var interpreted=SessionTimestampPlanV1.InterpretTradingHoursUtc(walls[i],th.TimeZoneInfo);
                Require(Same(interpreted.Query,expected[i]),"REFERENCE_CALENDAR_EXPECTATION_MISMATCH");
                references.Add(new { wall=Stamp(walls[i]),utc=Stamp(interpreted.Query),offset_ticks=interpreted.SourceOffsetTicks });
            }
            return new { name=th.Name,version=th.Version,zone_id=th.TimeZoneInfo.Id,zone_serialized=zone,zone_sha256=Hash(zone),
                sessions_hhmm=sessions,holidays=holidays,partials=partials,relevant_exception_policy="REJECT_2026_09_13_THROUGH_22",references=references };
        }
        private string CalendarText(TradingHours th)
        {
            operation="LOADED_CALENDAR";sourceIndex=-1;
            string text=Json(Calendar(th));Require(Encoding.UTF8.GetByteCount(text)<=MaximumCalendarBytes,"CALENDAR_BYTES_LIMIT");return text;
        }
        private string Configuration(BarsRequest r)
        {
            operation="REQUEST_CONFIGURATION";sourceIndex=-1;
            Require(r!=null,"REQUEST_MISSING");InstrumentContract(r.Instrument);PeriodContract(r.BarsPeriod);
            Require(r.LookupPolicy==LookupPolicies.Repository && r.MergePolicy==MergePolicy.DoNotMerge && r.IsResetOnNewTradingDay &&
                !r.IsDividendAdjusted && !r.IsSplitAdjusted,"REQUEST_POLICY_MISMATCH");
            // FromLocal/ToLocal are local-calendar dates, not UTC instants. Record their actual Kind.
            Require(r.FromLocal.Ticks==FromDate.Ticks && r.ToLocal.Ticks==ThroughDate.Ticks,"REQUEST_DATES_MISMATCH");
            return Json(new { instrument=r.Instrument.FullName,master=r.Instrument.MasterInstrument.Name,expiry_month="2026-12",
                tick_size=r.Instrument.MasterInstrument.TickSize,point_value=r.Instrument.MasterInstrument.PointValue,
                bars_period="Minute",period_value=1,market_data="Last",lookup="Repository",merge="DoNotMerge",reset_at_eod=true,
                dividend_adjusted=false,split_adjusted=false,date_semantics="REQUEST_LOCAL_CALENDAR_DATES",
                submitted_from=Stamp(FromDate),submitted_through=Stamp(ThroughDate),actual_from=Stamp(r.FromLocal),actual_through=Stamp(r.ToLocal) });
        }
        internal SessionTimestampNativeRequestV1 CreateAndWrap(object owner)
        {
            BarsRequest raw=null;
            try
            {
                return Run(owner,()=> {
                    Require(creates==0 && request==null,"REQUEST_FACTORY_ALREADY_USED");Environment();
                    operation="INSTRUMENT_LOOKUP";var instrument=Instrument.GetInstrument("NQ DEC26");InstrumentContract(instrument);
                    operation="TEMPLATE_LOOKUP";var th=TradingHours.Get(TemplateName);string canonical=CalendarText(th);
                    operation="REQUEST_CONSTRUCTOR";creates++;
                    raw=new BarsRequest(instrument,FromDate,ThroughDate);
                    operation="REQUEST_CONFIGURE";
                    raw.BarsPeriod=new BarsPeriod { BarsPeriodType=BarsPeriodType.Minute,Value=1,MarketDataType=MarketDataType.Last };
                    raw.TradingHours=th;raw.LookupPolicy=LookupPolicies.Repository;raw.MergePolicy=MergePolicy.DoNotMerge;
                    raw.IsResetOnNewTradingDay=true;raw.IsDividendAdjusted=false;raw.IsSplitAdjusted=false;
                    string config=Configuration(raw);Require(CalendarText(raw.TradingHours)==canonical,"CONFIG_CALENDAR_CHANGED");Environment();
                    var wrapped=new SessionTimestampNativeRequestV1(owner,raw,()=>CheckBeforeSubmit(owner));
                    Require(Read(ref failed)==0 && Read(ref invalidated)==0,"FACTORY_INTERRUPTED");
                    request=raw;requestedCalendar=raw.TradingHours;configuration=config;calendar=canonical;
                    return wrapped;
                });
                // Successful return transfers sole request lifetime ownership to C/E.
            }
            catch
            {
                // Covers failures both inside configuration AND in Run's final checkpoint.
                // raw is local to this attempt: a repeated/foreign call cannot close the owner.
                if(raw!=null) { cleanup++;try { raw.Dispose(); } catch { } }
                throw;
            }
        }
        private void BaseCheck()
        {
            Environment();Require(request!=null,"REQUEST_NOT_CREATED");
            Require(Object.ReferenceEquals(request.TradingHours,requestedCalendar),"REQUEST_CALENDAR_OBJECT_CHANGED");
            Require(Configuration(request)==configuration,"REQUEST_CONFIGURATION_CHANGED");
            Require(CalendarText(request.TradingHours)==calendar,"REQUEST_CALENDAR_CHANGED");
        }
        internal void CheckBeforeSubmit(object owner)
        { Run(owner,()=> { BaseCheck();return true; }); }
        private sealed class Measurement
        {
            internal int Count,Utc,Unspecified,Local,Increasing,Duplicates,Decreasing,Misaligned,Transitions;
            internal DateTime First,Last;
            internal string Hash;
            internal object Payload()
            { return new { hash_algorithm="R53F_SNAPSHOT_BITS_V1",rows=Count,first=Stamp(First),last=Stamp(Last),sha256=Hash,utc_count=Utc,unspecified_count=Unspecified,
                local_count=Local,increasing_pairs=Increasing,duplicate_pairs=Duplicates,decreasing_pairs=Decreasing,
                misaligned_count=Misaligned,kind_transitions=Transitions,interpretation="RAW_TICKS_AND_KIND_NOT_NORMALIZED" }; }
        }
        private Measurement Measure(Bars b)
        {
            operation="SNAPSHOT_COUNT";sourceIndex=-1;fullScans++;
            Require(b!=null && b.Count>=3 && b.Count<=MaximumRows,"SNAPSHOT_COUNT_OUT_OF_RANGE");
            var m=new Measurement { Count=b.Count };DateTime previous=DateTime.MinValue;
            using(var hash=SHA256.Create())
            {
                byte[] header=Encoding.UTF8.GetBytes("R53F_SNAPSHOT_BITS_V1|"+m.Count.ToString(CultureInfo.InvariantCulture)+"\n");
                hash.TransformBlock(header,0,header.Length,header,0);
                for(int i=0;i<m.Count;i++)
                {
                    sourceIndex=i;operation="SNAPSHOT_GET_TIME";DateTime t=b.GetTime(i);
                    if(i==0)m.First=t;m.Last=t;
                    if(t.Kind==DateTimeKind.Utc)m.Utc++;else if(t.Kind==DateTimeKind.Unspecified)m.Unspecified++;else m.Local++;
                    if(i>0) { if(t.Ticks>previous.Ticks)m.Increasing++;else if(t.Ticks==previous.Ticks)m.Duplicates++;else m.Decreasing++;if(t.Kind!=previous.Kind)m.Transitions++; }
                    if(t.Ticks%TimeSpan.TicksPerMinute!=0)m.Misaligned++;
                    operation="SNAPSHOT_GET_OHLCV";
                    long[] fields={i,t.Ticks,(long)t.Kind,BitConverter.DoubleToInt64Bits(b.GetOpen(i)),BitConverter.DoubleToInt64Bits(b.GetHigh(i)),
                        BitConverter.DoubleToInt64Bits(b.GetLow(i)),BitConverter.DoubleToInt64Bits(b.GetClose(i)),b.GetVolume(i)};
                    var parts=Array.ConvertAll(fields,x=>x.ToString(CultureInfo.InvariantCulture));
                    byte[] row=Encoding.UTF8.GetBytes(String.Join("|",parts)+"\n");
                    Require(row.Length<=1024,"SNAPSHOT_ROW_BYTES_LIMIT");hash.TransformBlock(row,0,row.Length,row,0);previous=t;
                }
                hash.TransformFinalBlock(new byte[0],0,0);m.Hash=Hex(hash.Hash);
            }
            operation="SNAPSHOT_FINAL_COUNT";Require(b.Count==m.Count,"SNAPSHOT_COUNT_CHANGED");
            Require(m.First.Kind==DateTimeKind.Unspecified,"A_NATIVE_KIND_NOT_UNSPECIFIED");
            Require(m.Last.Ticks>=m.First.Ticks,"RAW_ENDPOINT_RANGE_REVERSED");return m;
        }
        private void BarsContract(Bars b)
        {
            operation="BARS_CONFIGURATION";sourceIndex=-1;
            Require(b!=null,"BARS_MISSING");InstrumentContract(b.Instrument);PeriodContract(b.BarsPeriod);
            Require(CalendarText(b.TradingHours)==calendar,"RETURNED_CALENDAR_MISMATCH");
        }
        private void LightCheck()
        {
            BaseCheck();Require(bound && selectedBars!=null,"SNAPSHOT_NOT_BOUND");
            Require(Object.ReferenceEquals(request.Bars,selectedBars),"BARS_IDENTITY_CHANGED");
            Require(Object.ReferenceEquals(selectedBars.TradingHours,returnedCalendar),"BARS_CALENDAR_OBJECT_CHANGED");
            BarsContract(selectedBars);
            operation="BOUND_ENDPOINTS";
            Require(selectedBars.Count==snapshot.Count,"SNAPSHOT_COUNT_CHANGED");sourceIndex=0;DateTime first=selectedBars.GetTime(0);
            sourceIndex=snapshot.Count-1;DateTime last=selectedBars.GetTime(sourceIndex);
            Require(Same(first,snapshot.First) && Same(last,snapshot.Last),"SNAPSHOT_ENDPOINTS_CHANGED");
        }
        internal TimestampQueryPlan Bind(object owner,object callbackIdentity)
        {
            return Run(owner,()=> {
                Require(!bound,"SNAPSHOT_ALREADY_BOUND");BaseCheck();
                Require(Object.ReferenceEquals(callbackIdentity,request),"CALLBACK_REQUEST_IDENTITY_MISMATCH");
                var b=request.Bars;BarsContract(b);var before=Measure(b);BaseCheck();BarsContract(b);var after=Measure(b);
                Require(before.Count==after.Count && before.Hash==after.Hash,"SNAPSHOT_CHANGED_DURING_BIND");
                Require(Object.ReferenceEquals(request.Bars,b),"BARS_IDENTITY_CHANGED");
                selectedBars=b;returnedCalendar=b.TradingHours;snapshot=after;
                operation="PLAN_BINDING";sourceIndex=-1;
                plan=SessionTimestampPlanV1.Build(after.First,after.Last,after.Count,after.Hash,Hash(calendar),returnedCalendar.TimeZoneInfo);
                contextJson=Json(new { schema="arms.r53.loaded-context.v1",version=Version,classification="DIAGNOSTIC_ONLY",
                    request_configuration_json=configuration,request_configuration_sha256=Hash(configuration),
                    loaded_calendar_json=calendar,loaded_calendar_sha256=Hash(calendar),snapshot=after.Payload(),
                    source_index=0,source_timestamp=Stamp(after.First),request_constructor_attempts=creates,
                    application_timezone="UTC",sdk_version="8.1.8.2",sdk_core_mvid=typeof(BarsRequest).Assembly.ManifestModule.ModuleVersionId.ToString("D"),
                    playback_connected=false,operator_confirmations="ENABLED_MARKET_OPEN_DATA_FLOW_CONNECTION_STABLE_TRUE",
                    operator_observations_independently_verified=false,bar_timestamp_conversion=false,
                    native_provenance_attested=false,certification_evidence=false,runtime_admission=false,
                    validation_scope="LOADED_VALUES_CHECKED_AT_OBSERVATION_POINTS_NOT_PROVIDER_ATTESTATION" });
                Require(Encoding.UTF8.GetByteCount(contextJson)<=MaximumContextBytes,"CONTEXT_BYTES_LIMIT");
                BaseCheck();BarsContract(b);bound=true;LightCheck();return plan;
            });
        }
        internal Bars BoundBars(object owner)
        { return Run(owner,()=> { LightCheck();return selectedBars; }); }
        internal void Check(object owner,string phase,QueryControl control)
        {
            Run(owner,()=> {
                LightCheck();
                if(control!=null)
                {
                    bool member=false;foreach(var c in plan.Cases)if(Object.ReferenceEquals(c,control))member=true;
                    Require(member,"CONTROL_NOT_IN_BOUND_PLAN");
                }
                // Full byte-content scans at matrix entry/completion; lightweight gates before each SDK action.
                if(phase=="BEFORE_MATRIX" || phase=="BEFORE_COMPLETE")FullCheck();
                return true;
            });
        }
        private void FullCheck()
        {
            LightCheck();var current=Measure(selectedBars);
            Require(current.Count==snapshot.Count && current.Hash==snapshot.Hash,"SNAPSHOT_CONTENT_CHANGED");LightCheck();
        }
        internal void Revalidate(object owner)
        { Run(owner,()=> { FullCheck();return true; }); }
        internal void CheckLifecycle(object owner,string phase)
        {
            Run(owner,()=> {
                Environment();if(request!=null)BaseCheck();
                if(bound && (phase=="AFTER_PROCESS" || phase=="BEFORE_PREPARE" || phase=="AFTER_PREPARE"))FullCheck();
                return true;
            });
        }
        // Returns previously captured data only, never reads a disposed native request.
        // Future host must bind these exact bytes to the matrix and its completion seal.
        internal string CapturedContext(object owner)
        { Owner(owner);Require(bound && contextJson!=null,"CONTEXT_NOT_CAPTURED");return contextJson; }
    }
}
