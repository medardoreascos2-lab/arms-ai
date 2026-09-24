// R5.3-H: configured NinjaScript host for the reviewed A-G diagnostic chain.
// Disabled by default. No strategy, account, order, timer, reconnect or retry.
// Installation and one native activation require separate operator gates.
using System;
using System.ComponentModel.DataAnnotations;
using System.Threading;
using Arms.AI.Diagnostics.R53;
using NinjaTrader.Data;
using NinjaTrader.NinjaScript;

namespace NinjaTrader.NinjaScript.Indicators
{
    public class ArmsSessionTimestampInterpretationProbeV1 : Indicator
    {
        private readonly object hostSync = new object();
        private bool configured, dataLoadedSeen, terminated;
        private ProbeAttempt attempt;

        [NinjaScriptProperty]
        [Display(Name="Probe enabled",Order=1,GroupName="ARMS diagnostic only")]
        public bool ProbeEnabled { get; set; }
        [NinjaScriptProperty]
        [Display(Name="Fresh private output directory",Order=2,GroupName="ARMS diagnostic only")]
        public string OutputDirectory { get; set; }
        [NinjaScriptProperty]
        [Display(Name="Operator confirms market reopened",Order=3,GroupName="ARMS diagnostic only")]
        public bool MarketReopenConfirmed { get; set; }
        [NinjaScriptProperty]
        [Display(Name="Operator confirms NQ data flow",Order=4,GroupName="ARMS diagnostic only")]
        public bool NqDataFlowConfirmed { get; set; }
        [NinjaScriptProperty]
        [Display(Name="Operator confirms stable connection",Order=5,GroupName="ARMS diagnostic only")]
        public bool ConnectionStableConfirmed { get; set; }

        protected override void OnStateChange()
        {
            if(State == State.SetDefaults)
            {
                // Only UI defaults. Never allocate requests/writers or reset a live attempt.
                lock(hostSync)
                {
                    if(attempt != null && attempt.IsOwner(this))return;
                    Name="ArmsSessionTimestampInterpretationProbeV1";
                    Description="R5.3 bounded timestamp interpretation diagnostic; no trading authority.";
                    IsOverlay=true;IsChartOnly=true;
                    ProbeEnabled=false;OutputDirectory="";
                    MarketReopenConfirmed=false;NqDataFlowConfirmed=false;ConnectionStableConfirmed=false;
                }
            }
            else if(State == State.Configure)
            {
                lock(hostSync) { if(!terminated && !dataLoadedSeen)configured=true; }
            }
            else if(State == State.DataLoaded)
            {
                ProbeAttempt selected=null;
                lock(hostSync)
                {
                    if(dataLoadedSeen || terminated)return;
                    dataLoadedSeen=true;
                    // A shallow UI clone may share attempt, but must never operate on it.
                    if(!configured || !ProbeEnabled || attempt != null)return;
                    attempt=selected=new ProbeAttempt(this,OutputDirectory,Bars);
                }
                selected.Start(this);
            }
            else if(State == State.Terminated)
            {
                ProbeAttempt selected;
                lock(hostSync) { terminated=true;selected=attempt; }
                if(selected != null && selected.IsOwner(this))selected.Stop(this);
            }
        }

        protected override void OnBarUpdate() { }

        private TimestampOperatorSettings CurrentSettings(string expectedOutput,Bars expectedChart)
        {
            // Read data objects only after DataLoaded; no ChartControl/UI-thread dependency.
            bool enabled,open,flow,stable,stopped;string output;
            lock(hostSync)
            {
                enabled=ProbeEnabled;open=MarketReopenConfirmed;flow=NqDataFlowConfirmed;
                stable=ConnectionStableConfirmed;output=OutputDirectory;stopped=terminated;
            }
            if(stopped || State==State.Terminated)
                return new TimestampOperatorSettings(enabled,open,flow,stable,true,output);
            if(!enabled || !open || !flow || !stable || output!=expectedOutput)
                return new TimestampOperatorSettings(enabled,open,flow,stable,false,output);
            var b=Bars;
            if(b==null || !Object.ReferenceEquals(b,expectedChart))throw new InvalidOperationException("HOST_CHART_IDENTITY");
            var instrument=b.Instrument;var period=b.BarsPeriod;var calendar=b.TradingHours;
            if(instrument==null || instrument.MasterInstrument==null || instrument.FullName!="NQ DEC26" ||
                instrument.MasterInstrument.Name!="NQ" || instrument.Expiry.Year!=2026 || instrument.Expiry.Month!=12 ||
                instrument.MasterInstrument.TickSize!=.25 || instrument.MasterInstrument.PointValue!=20)
                throw new InvalidOperationException("HOST_CHART_INSTRUMENT");
            if(period==null || period.BarsPeriodType!=BarsPeriodType.Minute || period.Value!=1 || period.MarketDataType!=MarketDataType.Last)
                throw new InvalidOperationException("HOST_CHART_PERIOD");
            if(calendar==null || calendar.Name!=SessionTimestampNativeContextV1.TemplateName || calendar.TimeZoneInfo==null ||
                calendar.TimeZoneInfo.Id!=SessionTimestampNativeContextV1.ZoneId)
                throw new InvalidOperationException("HOST_CHART_TEMPLATE");
            // F independently validates the full calendar on the requested/returned Bars.
            return new TimestampOperatorSettings(enabled,open,flow,stable,false,output);
        }

        internal ProbeHostObservation InspectDiagnostic()
        {
            ProbeAttempt selected;
            lock(hostSync)selected=attempt;
            if(selected==null)return new ProbeHostObservation("NOT_STARTED","NONE","NONE",null,0,false);
            if(!selected.IsOwner(this))return new ProbeHostObservation("NON_OWNER_CLONE","NONE","NONE",null,0,false);
            return selected.Inspect(this);
        }

        private void Notify(string status,string guard,string error,string contextGuard,string contextOperation,int contextIndex)
        {
            // One bounded, redacted notification. No path, provider message or stack.
            try { Print("ARMS_R53_H STATUS="+status+" GUARD="+guard+" ERROR_TYPE="+error+
                " CONTEXT_GUARD="+contextGuard+" CONTEXT_OPERATION="+contextOperation+" CONTEXT_INDEX="+contextIndex); }
            catch { /* A notification failure grants no execution or retry authority. */ }
        }

        private sealed class ProbeAttempt
        {
            private readonly ProbeAttempt self;
            private readonly ArmsSessionTimestampInterpretationProbeV1 host;
            private readonly object finishSync=new object();
            private readonly string folder;
            private readonly Bars chart;
            private SessionTimestampLifecycleV1 life;
            private SessionTimestampNativeContextV1 context;
            private SessionTimestampContextEnvelopeV1 writer;
            private SessionTimestampNativeCursorFactoryV1 cursors;
            private TimestampQueryPlan plan;
            private int started,stopping,publicationAttempts,notified;
            private string status="CREATED_NOT_STARTED",guard="NONE",errorType="NONE";
            private bool sealedOk;

            internal ProbeAttempt(ArmsSessionTimestampInterpretationProbeV1 owner,string output,Bars hostBars)
            { self=this;host=owner;folder=output;chart=hostBars; }
            internal bool IsOwner(ArmsSessionTimestampInterpretationProbeV1 owner)
            { return Object.ReferenceEquals(self,this) && Object.ReferenceEquals(host,owner); }
            private static int Read(ref int value) { return Interlocked.CompareExchange(ref value,0,0); }
            private void Owner(ArmsSessionTimestampInterpretationProbeV1 owner)
            { if(!IsOwner(owner))throw new InvalidOperationException("HOST_ATTEMPT_NOT_OWNER"); }
            private static string SafeType(Exception e)
            { return e is InvalidOperationException?"InvalidOperationException":e is ArgumentException?"ArgumentException":"OTHER"; }
            private static string SafeToken(string text)
            {
                if(String.IsNullOrEmpty(text) || text.Length>96)return "UNSPECIFIED_GUARD";
                foreach(char c in text)if(!(c>='A' && c<='Z') && !(c>='0' && c<='9') && c!='_')return "UNSPECIFIED_GUARD";
                return text;
            }
            private void Reject(string why,Exception error)
            {
                lock(finishSync)
                {
                    if(sealedOk)return;
                    status="FAILED_CLOSED";
                    if(guard=="NONE")guard=SafeToken(why);
                    if(errorType=="NONE" && error!=null)errorType=SafeType(error);
                }
            }
            internal void Start(ArmsSessionTimestampInterpretationProbeV1 owner)
            {
                Owner(owner);
                if(Interlocked.CompareExchange(ref started,1,0)!=0)return;
                try
                {
                    if(Read(ref stopping)!=0)throw new InvalidOperationException("HOST_ALREADY_STOPPED");
                    life=new SessionTimestampLifecycleV1(host);
                    context=new SessionTimestampNativeContextV1(host,
                        ()=>host.CurrentSettings(folder,chart),folder);
                    lock(finishSync)status="PENDING";
                    life.Start(host,true,
                        ()=> {
                            writer=new SessionTimestampContextEnvelopeV1(host,life,context,folder,
                                Guid.NewGuid().ToString("D"),Guid.NewGuid().ToString("D"),"OPERATOR_NATIVE_RUN_UNATTESTED");
                            return writer;
                        },
                        ()=> {
                            var raw=context.CreateAndWrap(host);
                            try { return new ObservedRequest(this,raw); }
                            catch { raw.Dispose();throw; }
                        },
                        (request,checkpoint)=> {
                            plan=context.Bind(host,request.Identity);
                            cursors=new SessionTimestampNativeCursorFactoryV1(context.BoundBars(host),plan,checkpoint,
                                (phase,c)=>context.Check(host,phase,c));
                            var report=new SessionTimestampExecutorV1().Execute(plan,cursors.Create,cursors.Check);
                            context.Revalidate(host);return report;
                        },
                        report=>writer.Prepare(host,plan,report),
                        phase=> {
                            if(Read(ref stopping)!=0)throw new InvalidOperationException("HOST_STOPPED");
                            context.CheckLifecycle(host,phase);
                        });
                }
                catch(Exception error)
                {
                    Reject("HOST_START_FAILED",error);
                    if(life!=null)life.Terminate(host);
                }
                finally { FinishObservation(); }
            }
            internal void Stop(ArmsSessionTimestampInterpretationProbeV1 owner)
            {
                Owner(owner);Interlocked.Exchange(ref stopping,1);
                // C cooperatively stops in-flight work and closes resources after its last user.
                if(life!=null)life.Terminate(host);
                FinishObservation();
            }
            private void FinishObservation()
            {
                try
                {
                    lock(finishSync)
                    {
                        if(life==null)
                        {
                            if(Read(ref stopping)!=0) { status="FAILED_CLOSED";guard="TERMINATED_BEFORE_START"; }
                        }
                        else
                        {
                            var state=life.Inspect(host);
                            if(state.ReadyForSeal && !sealedOk && publicationAttempts==0 && Read(ref stopping)==0 && status!="FAILED_CLOSED")
                            {
                                publicationAttempts++;
                                // G rechecks environment/files and reads only cached context here.
                                writer.PublishSeal(host);
                                sealedOk=writer.Sealed;
                                if(!sealedOk)throw new InvalidOperationException("HOST_SEAL_NOT_PUBLISHED");
                                status="SEALED_DIAGNOSTIC_ONLY";
                            }
                            else if(!sealedOk && (state.Status=="FAILED_CLOSED" || Read(ref stopping)!=0))
                            {
                                status="FAILED_CLOSED";guard=SafeToken(state.StopGuard=="NONE"?"HOST_TERMINATED":state.StopGuard);
                                errorType=(state.ExceptionType=="NONE" || state.ExceptionType=="InvalidOperationException" ||
                                    state.ExceptionType=="ArgumentException" || state.ExceptionType=="ObjectDisposedException" ||
                                    state.ExceptionType=="NullReferenceException")?state.ExceptionType:"OTHER";
                            }
                        }
                    }
                }
                catch(Exception error) { Reject("HOST_PUBLICATION_FAILED",error); }
                string s,g,e;
                lock(finishSync) { s=status;g=guard;e=errorType; }
                if((s=="FAILED_CLOSED" || s=="SEALED_DIAGNOSTIC_ONLY") && Interlocked.CompareExchange(ref notified,1,0)==0)
                    host.Notify(s,g,e,context==null?"NONE":SafeToken(context.FailureGuard),
                        context==null?"NONE":SafeToken(context.FailureOperation),context==null?-1:context.FailureSourceIndex);
            }
            internal ProbeHostObservation Inspect(ArmsSessionTimestampInterpretationProbeV1 owner)
            {
                Owner(owner);
                lock(finishSync)return new ProbeHostObservation(status,guard,errorType,
                    life==null?null:life.Inspect(host),publicationAttempts,sealedOk);
            }
            private sealed class ObservedRequest : ISessionTimestampRequestV1
            {
                private readonly ObservedRequest self;
                private readonly ProbeAttempt owner;
                private readonly SessionTimestampNativeRequestV1 inner;
                internal ObservedRequest(ProbeAttempt parent,SessionTimestampNativeRequestV1 value)
                { self=this;owner=parent;inner=value; }
                private void Owner()
                { if(!Object.ReferenceEquals(self,this))throw new InvalidOperationException("HOST_REQUEST_CLONE"); }
                public object Identity { get { Owner();return inner.Identity; } }
                public void Submit(Action<object,bool> callback)
                {
                    Owner();
                    inner.Submit((sender,ok)=> {
                        try { callback(sender,ok); }
                        finally { owner.FinishObservation(); }
                    });
                }
                public void Dispose()
                { if(Object.ReferenceEquals(self,this))inner.Dispose(); }
            }
        }
    }
}

namespace Arms.AI.Diagnostics.R53
{
    // Read-only in-process diagnostic state; not a seal or native provenance assertion.
    internal sealed class ProbeHostObservation
    {
        internal readonly string Status,Guard,ExceptionType;
        internal readonly TimestampLifecycleSnapshot Lifecycle;
        internal readonly int PublicationAttempts;
        internal readonly bool Sealed;
        internal ProbeHostObservation(string status,string guard,string error,TimestampLifecycleSnapshot life,int publications,bool sealedOk)
        { Status=status;Guard=guard;ExceptionType=error;Lifecycle=life;PublicationAttempts=publications;Sealed=sealedOk; }
    }
}
