// R5.3-C: owner-bound request/callback/resource lifecycle; OFFLINE core only.
// No NinjaTrader types, disk writer, completion seal, or provider connections here.
// Future adapters must implement current context checks and durable evidence separately.
using System;

namespace Arms.AI.Diagnostics.R53
{
    internal sealed class LifecycleGuardException : InvalidOperationException
    {
        public string GuardId { get; private set; }
        internal LifecycleGuardException(string id) : base(id) { GuardId = id; }
    }

    internal interface ISessionTimestampRequestV1 : IDisposable
    {
        // Return the actual underlying request object, not an invented string/UUID.
        object Identity { get; }
        void Submit(Action<object, bool> callback);
    }

    internal sealed class TimestampLifecycleSnapshot
    {
        public string Status { get; private set; }
        public string StopGuard { get; private set; }
        public string ExceptionType { get; private set; }
        public int WriterFactoryAttempts { get; private set; }
        public int RequestFactoryAttempts { get; private set; }
        public int SubmitAttempts { get; private set; }
        public int ProcessAttempts { get; private set; }
        public int PreparationAttempts { get; private set; }
        public int RequestDisposeAttempts { get; private set; }
        public int WriterDisposeAttempts { get; private set; }
        public int DuplicateCallbacks { get; private set; }
        public bool SubmitReturned { get; private set; }
        public bool RequestClosed { get; private set; }
        public bool WriterClosed { get; private set; }
        // Disposal pass has finished; successful closure is attested by the two Closed flags.
        public bool ResourcesReleased { get; private set; }
        // Only a prerequisite for a FUTURE evidence writer. This is not a seal.
        public bool ReadyForSeal { get; private set; }
        public TimestampMatrixReport Matrix { get; private set; }
        public bool SealWritten { get { return false; } }
        public bool NativeProvenanceAttested { get { return false; } }
        public bool HistoricalAdmission { get { return false; } }
        internal TimestampLifecycleSnapshot(string status, string guard, string error,
            int writerCreates, int requestCreates, int submits, int processes, int prepares,
            int requestDisposes, int writerDisposes, int duplicates, bool returned,
            bool requestClosed, bool writerClosed, bool released, bool ready, TimestampMatrixReport matrix)
        {
            Status=status; StopGuard=guard; ExceptionType=error;
            WriterFactoryAttempts=writerCreates; RequestFactoryAttempts=requestCreates;
            SubmitAttempts=submits; ProcessAttempts=processes; PreparationAttempts=prepares;
            RequestDisposeAttempts=requestDisposes; WriterDisposeAttempts=writerDisposes;
            DuplicateCallbacks=duplicates; SubmitReturned=returned; RequestClosed=requestClosed;
            WriterClosed=writerClosed; ResourcesReleased=released; ReadyForSeal=ready; Matrix=matrix;
        }
    }

    internal sealed class SessionTimestampLifecycleV1
    {
        private readonly object sync = new object();
        private readonly SessionTimestampLifecycleV1 instanceOwner;
        private readonly object hostOwner;
        private bool started, terminated, failed, submitReturned, callbackClaimed, processed;
        private bool finalizing, releasing, released, completed, prepared;
        private bool requestClosed, writerClosed;
        private int active, writerCreates, requestCreates, submits, processes, prepares;
        private int requestDisposes, writerDisposes, duplicates;
        private string stopGuard="NONE", errorType="NONE";
        private IDisposable writer;
        private ISessionTimestampRequestV1 request;
        private object requestIdentity;
        private TimestampMatrixReport matrix;
        private Func<ISessionTimestampRequestV1, Action, TimestampMatrixReport> process;
        private Action<TimestampMatrixReport> prepare;
        private Action<string> context;

        internal SessionTimestampLifecycleV1(object owner)
        {
            if (owner == null) throw new ArgumentNullException("owner");
            instanceOwner=this; hostOwner=owner;
        }

        internal bool IsOwner(object owner)
        {
            return Object.ReferenceEquals(this, instanceOwner) && Object.ReferenceEquals(owner, hostOwner);
        }
        private void Owner(object owner)
        {
            if (!IsOwner(owner)) throw new LifecycleGuardException("LIFECYCLE_NOT_OWNER");
        }
        private static string SafeError(Exception error)
        {
            if (error is ObjectDisposedException) return "ObjectDisposedException";
            if (error is InvalidOperationException) return "InvalidOperationException";
            if (error is ArgumentException) return "ArgumentException";
            if (error is NullReferenceException) return "NullReferenceException";
            return "OTHER";
        }
        private void Stop(string guard, string error)
        {
            lock(sync)
            {
                if (completed) return;
                if (!failed) { stopGuard=guard; errorType=error; }
                failed=true;
            }
        }
        private void Checkpoint()
        {
            lock(sync)
            {
                if (failed || terminated) throw new LifecycleGuardException("LIFECYCLE_STOPPED");
            }
        }
        private void CheckContext(string phase)
        {
            Checkpoint();
            try { context(phase); }
            catch (Exception error)
            {
                Stop("CONTEXT_" + phase, SafeError(error));
                throw new LifecycleGuardException("LIFECYCLE_STOPPED");
            }
            Checkpoint();
        }
        private void CheckIdentity()
        {
            Checkpoint();
            object identity;
            try { identity=request.Identity; }
            catch (Exception error)
            {
                Stop("REQUEST_IDENTITY_ACCESS", SafeError(error));
                throw new LifecycleGuardException("LIFECYCLE_STOPPED");
            }
            if (identity == null || !Object.ReferenceEquals(identity, requestIdentity))
            {
                Stop("REQUEST_IDENTITY_CHANGED", "NONE");
                throw new LifecycleGuardException("LIFECYCLE_STOPPED");
            }
            Checkpoint();
        }

        // Factories return NEW, exclusively-owned resources. Failure inside a factory before
        // ownership is transferred must clean its own partially constructed resource.
        // prepareEvidence must serialize diagnostic data ONLY; it must NOT publish a seal.
        // Future adapters must call the supplied checkpoint before EVERY matrix/native action.
        internal void Start(object owner, bool enabled, Func<IDisposable> writerFactory,
            Func<ISessionTimestampRequestV1> requestFactory,
            Func<ISessionTimestampRequestV1, Action, TimestampMatrixReport> processor,
            Action<TimestampMatrixReport> prepareEvidence, Action<string> contextCheck)
        {
            Owner(owner);
            bool consumed=false;
            lock(sync)
            {
                if (!enabled) return;
                if (started || terminated || failed || released)
                {
                    if (started && !released) Stop("START_REENTRANT_OR_REPEATED", "NONE");
                    consumed=true;
                }
                else
                {
                    started=true; active++;
                    process=processor; prepare=prepareEvidence; context=contextCheck;
                }
            }
            if (consumed)
            {
                Progress();
                throw new LifecycleGuardException("START_ALREADY_CONSUMED");
            }
            string phase="DEPENDENCIES";
            try
            {
                if (writerFactory == null || requestFactory == null || processor == null ||
                    prepareEvidence == null || contextCheck == null)
                    throw new LifecycleGuardException("DEPENDENCIES_MISSING");
                CheckContext("BEFORE_OPEN");
                phase="WRITER_FACTORY";
                lock(sync) { Checkpoint(); writerCreates++; }
                IDisposable w=writerFactory();
                lock(sync) { writer=w; }
                Checkpoint();
                if (w == null) throw new LifecycleGuardException("WRITER_FACTORY_RETURNED_NULL");
                CheckContext("BEFORE_REQUEST_CREATE");
                phase="REQUEST_FACTORY";
                lock(sync) { Checkpoint(); requestCreates++; }
                ISessionTimestampRequestV1 r=requestFactory();
                lock(sync) { request=r; }
                Checkpoint();
                if (r == null) throw new LifecycleGuardException("REQUEST_FACTORY_RETURNED_NULL");
                if (Object.ReferenceEquals(w,r)) throw new LifecycleGuardException("RESOURCE_ALIAS");
                phase="REQUEST_IDENTITY";
                object id=r.Identity;
                Checkpoint();
                if (id == null) throw new LifecycleGuardException("REQUEST_IDENTITY_MISSING");
                lock(sync) { requestIdentity=id; }
                CheckContext("BEFORE_SUBMIT");
                CheckIdentity();
                phase="REQUEST_SUBMIT";
                lock(sync) { Checkpoint(); submits++; }
                r.Submit((sender, success) => Callback(owner, sender, success));
                Checkpoint();
                lock(sync) { submitReturned=true; }
                CheckContext("AFTER_SUBMIT");
            }
            catch (LifecycleGuardException error) { Stop(error.GuardId, "NONE"); }
            catch (Exception error) { Stop(phase, SafeError(error)); }
            finally
            {
                lock(sync) { active--; }
                Progress();
            }
        }

        internal void Callback(object owner, object sender, bool success)
        {
            Owner(owner);
            bool execute=false;
            lock(sync)
            {
                // Late callbacks after release begins are ignored. No retries, writes or cleanup.
                if (failed || terminated || releasing || released || completed) return;
                if (!started || submits != 1) Stop("CALLBACK_BEFORE_SUBMIT", "NONE");
                else if (callbackClaimed)
                {
                    if (duplicates < Int32.MaxValue) duplicates++;
                    Stop("CALLBACK_DUPLICATE_BEFORE_RELEASE", "NONE");
                }
                else
                {
                    callbackClaimed=true; active++; execute=true;
                }
            }
            if (!execute) { Progress(); return; }
            string phase="CALLBACK_IDENTITY";
            try
            {
                Checkpoint();
                if (sender == null || !Object.ReferenceEquals(sender,requestIdentity))
                    throw new LifecycleGuardException("CALLBACK_IDENTITY_MISMATCH");
                CheckIdentity();
                if (!success) throw new LifecycleGuardException("CALLBACK_ERROR");
                CheckContext("BEFORE_PROCESS");
                phase="PROCESSOR";
                lock(sync) { Checkpoint(); processes++; }
                TimestampMatrixReport result=process(request, Checkpoint);
                Checkpoint();
                if (result == null || !result.MatrixCompleted)
                    throw new LifecycleGuardException("MATRIX_INCOMPLETE");
                CheckIdentity();
                CheckContext("AFTER_PROCESS");
                lock(sync) { matrix=result; processed=true; }
            }
            catch (LifecycleGuardException error) { Stop(error.GuardId, "NONE"); }
            catch (Exception error) { Stop(phase, SafeError(error)); }
            finally
            {
                lock(sync) { active--; }
                Progress();
            }
        }

        internal void Terminate(object owner)
        {
            Owner(owner);
            lock(sync)
            {
                if (released || completed) return;
                terminated=true;
                Stop(started ? "TERMINATED_INCOMPLETE" : "TERMINATED_BEFORE_START", "NONE");
            }
            Progress();
        }

        // Never hold sync across provider/factory/processor/writer operations. Cancellation
        // is cooperative: an operation already in flight may finish, but cannot complete
        // this attempt; resources are not disposed while that operation is using them.
        private void Progress()
        {
            bool finish=false;
            lock(sync)
            {
                if (active != 0 || finalizing || releasing || released) return;
                if (!failed && !(started && submitReturned && processed)) return;
                finalizing=true; active++;
                finish=!failed;
            }
            try
            {
                if (finish)
                {
                    CheckContext("BEFORE_PREPARE");
                    CheckIdentity();
                    lock(sync) { Checkpoint(); prepares++; }
                    prepare(matrix);
                    Checkpoint();
                    CheckIdentity();
                    CheckContext("AFTER_PREPARE");
                    lock(sync) { prepared=true; }
                }
            }
            catch (LifecycleGuardException error) { Stop(error.GuardId, "NONE"); }
            catch (Exception error) { Stop("EVIDENCE_PREPARATION", SafeError(error)); }
            finally
            {
                lock(sync) { active--; releasing=true; }
                ReleaseResources();
            }
        }

        private void ReleaseResources()
        {
            ISessionTimestampRequestV1 r;
            IDisposable w;
            lock(sync) { r=request; w=writer; request=null; writer=null; }
            bool same=r != null && Object.ReferenceEquals(r,w);
            bool rClosed=r==null, wClosed=w==null;
            if (r != null)
            {
                lock(sync) { requestDisposes++; }
                try { r.Dispose(); rClosed=true; }
                catch (Exception error) { Stop("REQUEST_DISPOSE", SafeError(error)); }
            }
            if (same) wClosed=rClosed;
            else if (w != null)
            {
                lock(sync) { writerDisposes++; }
                try { w.Dispose(); wClosed=true; }
                catch (Exception error) { Stop("WRITER_DISPOSE", SafeError(error)); }
            }
            lock(sync)
            {
                requestClosed=rClosed; writerClosed=wClosed; released=true;
                completed=!failed && !terminated && submitReturned && processed && prepared &&
                    rClosed && wClosed;
                releasing=false; finalizing=false;
            }
        }

        internal TimestampLifecycleSnapshot Inspect(object owner)
        {
            Owner(owner);
            lock(sync)
            {
                string status=completed ? "READY_FOR_SEAL_NOT_SEALED" : failed ? "FAILED_CLOSED" :
                    !started ? "IDLE_DISABLED" : finalizing ? "FINALIZING" : "PENDING";
                return new TimestampLifecycleSnapshot(status, stopGuard, errorType, writerCreates,
                    requestCreates, submits, processes, prepares, requestDisposes, writerDisposes,
                    duplicates, submitReturned, requestClosed, writerClosed, released, completed, matrix);
            }
        }
    }
}
