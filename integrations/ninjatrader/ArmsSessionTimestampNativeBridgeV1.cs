// R5.3-E: SDK request/cursor bridge. NOT an Indicator and never self-starts.
// Only compile against the installed SDK; synthetic tests use explicit doubles.
// The future host must validate the loaded request/calendar/snapshot and supply
// a lifecycle checkpoint plus context validator before allowing native calls.
using System;
using System.Collections.Generic;
using System.Threading;
using NinjaTrader.Cbi;
using NinjaTrader.Data;

namespace Arms.AI.Diagnostics.R53
{
    internal sealed class NativeBridgeGuardException : InvalidOperationException
    {
        public string GuardId { get; private set; }
        internal NativeBridgeGuardException(string id) : base(id) { GuardId=id; }
    }

    // C owns this wrapper exclusively after its request factory returns it.
    // Construction/configuration of the raw BarsRequest belongs to the future host.
    internal sealed class SessionTimestampNativeRequestV1 : ISessionTimestampRequestV1
    {
        private readonly object sync=new object(), hostOwner;
        private readonly SessionTimestampNativeRequestV1 instanceOwner;
        private readonly BarsRequest request;
        private readonly Action beforeSubmit;
        private bool submitted, submitting, disposeAttempted;
        private int nativeSubmitAttempts, nativeDisposeAttempts, forwardedCallbacks;

        internal SessionTimestampNativeRequestV1(object owner, BarsRequest raw, Action validateBeforeSubmit)
        {
            if(owner==null || raw==null || validateBeforeSubmit==null)
                throw new NativeBridgeGuardException("REQUEST_DEPENDENCY_MISSING");
            hostOwner=owner;instanceOwner=this;request=raw;beforeSubmit=validateBeforeSubmit;
        }
        private void Owner()
        {
            if(!Object.ReferenceEquals(this,instanceOwner))
                throw new NativeBridgeGuardException("REQUEST_CLONE_NOT_OWNER");
        }
        internal bool IsOwner(object owner)
        { return Object.ReferenceEquals(this,instanceOwner) && Object.ReferenceEquals(owner,hostOwner); }
        public object Identity { get { Owner();return request; } }
        internal int NativeSubmitAttempts { get { Owner();lock(sync)return nativeSubmitAttempts; } }
        internal int NativeDisposeAttempts { get { Owner();lock(sync)return nativeDisposeAttempts; } }
        internal int ForwardedCallbacks { get { Owner();lock(sync)return forwardedCallbacks; } }
        public void Submit(Action<object,bool> delivery)
        {
            Owner();
            if(delivery==null)throw new NativeBridgeGuardException("DELIVERY_MISSING");
            lock(sync)
            {
                if(submitted || disposeAttempted)throw new NativeBridgeGuardException("REQUEST_ALREADY_CONSUMED");
                submitted=true;submitting=true;
            }
            try
            {
                beforeSubmit();
                lock(sync)nativeSubmitAttempts++;
                request.Request((sender,error,ignoredMessage)=> {
                    lock(sync)
                    {
                        if(disposeAttempted)return;
                        if(forwardedCallbacks<Int32.MaxValue)forwardedCallbacks++;
                    }
                    // Preserve the ACTUAL callback sender. C rejects null/foreign identities.
                    // No provider text is forwarded, logged, stored or interpreted.
                    delivery(sender,error==ErrorCode.NoError);
                });
            }
            finally { lock(sync)submitting=false; }
        }
        public void Dispose()
        {
            // A shallow clone must not close the original request.
            if(!Object.ReferenceEquals(this,instanceOwner))return;
            lock(sync)
            {
                if(disposeAttempted)return;
                if(submitting)throw new NativeBridgeGuardException("DISPOSE_DURING_SUBMIT");
                disposeAttempted=true;nativeDisposeAttempts++;
            }
            // Charge once even if the native Dispose throws. C will forbid a seal.
            request.Dispose();
        }
    }

    internal sealed class SessionTimestampNativeCursorFactoryV1
    {
        private readonly SessionTimestampNativeCursorFactoryV1 instanceOwner;
        private readonly Bars bars;
        private readonly TimestampQueryPlan plan;
        private readonly Action checkpoint;
        private readonly Action<string,QueryControl> validateContext;
        private readonly HashSet<string> chargedSlots=new HashSet<string>(StringComparer.Ordinal);
        private int busy, checking, failed, invalidated, constructors, calls, begins, ends;

        internal SessionTimestampNativeCursorFactoryV1(Bars selectedBars,TimestampQueryPlan queryPlan,
            Action lifecycleCheckpoint,Action<string,QueryControl> contextValidator)
        {
            if(selectedBars==null || queryPlan==null || lifecycleCheckpoint==null || contextValidator==null)
                throw new NativeBridgeGuardException("CURSOR_FACTORY_DEPENDENCY_MISSING");
            instanceOwner=this;bars=selectedBars;plan=queryPlan;checkpoint=lifecycleCheckpoint;
            validateContext=contextValidator;
        }
        private static int Read(ref int value) { return Interlocked.CompareExchange(ref value,0,0); }
        private void Owner()
        {
            if(!Object.ReferenceEquals(this,instanceOwner))throw new NativeBridgeGuardException("FACTORY_CLONE_NOT_OWNER");
        }
        private void Need(bool ok,string id)
        {
            if(!ok) { Interlocked.Exchange(ref failed,1);throw new NativeBridgeGuardException(id); }
        }
        internal int ConstructorAttempts { get { Owner();return Read(ref constructors); } }
        internal int CallAttempts { get { Owner();return Read(ref calls); } }
        internal int BeginReadAttempts { get { Owner();return Read(ref begins); } }
        internal int EndReadAttempts { get { Owner();return Read(ref ends); } }
        internal bool Failed { get { Owner();return Read(ref failed)!=0; } }
        internal void Invalidate()
        {
            // Non-owning UI clones must not invalidate the original's resources.
            if(!Object.ReferenceEquals(this,instanceOwner))return;
            Interlocked.Exchange(ref invalidated,1);
        }
        internal void Check(string phase,QueryControl control)
        {
            Owner();Need(Read(ref failed)==0 && Read(ref invalidated)==0,"BRIDGE_NOT_USABLE");
            Need(Interlocked.CompareExchange(ref checking,1,0)==0,"CONTEXT_REENTRANT");
            try
            {
                checkpoint();validateContext(phase,control);checkpoint();
                Need(Read(ref failed)==0 && Read(ref invalidated)==0,"BRIDGE_CONTEXT_CHANGED");
            }
            catch
            {
                Interlocked.Exchange(ref failed,1);
                throw new NativeBridgeGuardException("BRIDGE_CONTEXT_REJECTED");
            }
            finally { Interlocked.Exchange(ref checking,0); }
        }
        private void Enter(string phase,QueryControl control)
        {
            Owner();Need(Interlocked.CompareExchange(ref busy,1,0)==0,"BRIDGE_OPERATION_REENTRANT");
            try { Check(phase,control); }
            catch { Interlocked.Exchange(ref busy,0);throw; }
        }
        private void Leave() { Interlocked.Exchange(ref busy,0); }
        private bool Member(QueryControl c)
        {
            if(c==null)return false;
            foreach(var expected in plan.Cases)if(Object.ReferenceEquals(c,expected))return true;
            return false;
        }
        internal ISessionTimestampCursor Create(QueryControl control)
        {
            Enter("SDK_BEFORE_CONSTRUCTOR",control);
            try
            {
                Need(Member(control) && !control.Reuse && control.ConstructorContext=="Bars" && control.IncludeEndTime,
                    "CONSTRUCTOR_CONTROL_INVALID");
                Need(constructors<SessionTimestampPlanV1.MaximumIteratorSlots,"NATIVE_CONSTRUCTOR_LIMIT");
                Need(chargedSlots.Add(control.IteratorId),"ITERATOR_SLOT_ALREADY_ATTEMPTED");
                constructors++;
                // Exactly one native constructor site. No fallback/TradingHours constructor.
                var iterator=new SessionIterator(bars);
                return new Cursor(this,iterator,control);
            }
            finally { Leave(); }
        }
        private sealed class Cursor : ISessionTimestampCursor
        {
            private readonly Cursor instanceOwner;
            private readonly SessionTimestampNativeCursorFactoryV1 factory;
            private readonly SessionIterator iterator;
            private readonly QueryControl initial;
            private int attempts;
            private bool returnedTrue, beginAttempted, endAttempted;
            private DateTime? begin, end;
            private QueryControl active;
            internal Cursor(SessionTimestampNativeCursorFactoryV1 parent,SessionIterator native,QueryControl control)
            { instanceOwner=this;factory=parent;iterator=native;initial=control;active=control; }
            private void Owner()
            { if(!Object.ReferenceEquals(this,instanceOwner))throw new NativeBridgeGuardException("CURSOR_CLONE_NOT_OWNER"); }
            public object Identity { get { Owner();return iterator; } }
            public bool Advance(DateTime query,bool includeEndTime)
            {
                Owner();
                QueryControl expected=attempts==1 && initial.CaseId=="R0" ? factory.plan.Cases[10] : initial;
                factory.Enter("SDK_BEFORE_ADVANCE",expected);
                try
                {
                    QueryControl c=initial;
                    if(attempts>0)
                    {
                        factory.Need(initial.CaseId=="R0" && attempts==1 && returnedTrue && begin.HasValue && end.HasValue &&
                            begin.Value.Kind==end.Value.Kind && end.Value.Ticks>begin.Value.Ticks,"CURSOR_REUSE_NOT_ALLOWED");
                        c=factory.plan.Cases[10];
                    }
                    factory.Need(query.Ticks==c.Time.Query.Ticks && query.Kind==c.Time.Query.Kind && includeEndTime==c.IncludeEndTime,
                        "NATIVE_QUERY_CHANGED");
                    factory.Need(factory.calls<SessionTimestampPlanV1.MaximumPlannedCalls,"NATIVE_CALL_LIMIT");
                    active=c;attempts++;factory.calls++;returnedTrue=false;
                    beginAttempted=false;endAttempted=false;begin=null;end=null;
                    // Pass the original DateTime and inclusion flag, without any conversion.
                    bool result=iterator.GetNextSession(query,includeEndTime);
                    returnedTrue=result;return result;
                }
                finally { factory.Leave(); }
            }
            public DateTime ReadBegin()
            {
                Owner();factory.Enter("SDK_BEFORE_BEGIN",active);
                try
                {
                    factory.Need(returnedTrue && !beginAttempted,"BEGIN_READ_NOT_ALLOWED");
                    beginAttempted=true;factory.begins++;
                    DateTime value=iterator.ActualSessionBegin;begin=value;return value;
                }
                finally { factory.Leave(); }
            }
            public DateTime ReadEnd()
            {
                Owner();factory.Enter("SDK_BEFORE_END",active);
                try
                {
                    factory.Need(returnedTrue && begin.HasValue && !endAttempted,"END_READ_NOT_ALLOWED");
                    endAttempted=true;factory.ends++;
                    DateTime value=iterator.ActualSessionEnd;end=value;return value;
                }
                finally { factory.Leave(); }
            }
        }
    }
}
