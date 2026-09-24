// R5.3-D: bounded diagnostic persistence, not a NinjaScript/native adapter.
// Owns only newly-created files. Never overwrites, removes or admits history.
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Security.Cryptography;
using System.Text;
using System.Web.Script.Serialization;

namespace Arms.AI.Diagnostics.R53
{
    internal sealed class EvidenceGuardException : InvalidOperationException
    {
        public string GuardId { get; private set; }
        internal EvidenceGuardException(string id) : base(id) { GuardId=id; }
    }

    internal sealed class SessionTimestampEvidenceV1 : IDisposable
    {
        internal const string Version="R5.3-D/evidence/1";
        internal const int MaximumRecords=96, MaximumBytes=262144, MaximumRecordBytes=32768;
        internal const string DiagnosticName="session-timestamp-evidence.jsonl";
        internal const string SealName="session-timestamp-evidence.done.json";
        private readonly object sync=new object(), hostOwner;
        private readonly SessionTimestampEvidenceV1 instanceOwner;
        private readonly SessionTimestampLifecycleV1 lifecycle;
        private readonly string directory, origin, probeId, requestId;
        private FileStream stream;
        private SHA256 runningHash;
        private int records, bytes;
        private bool failed, prepared, closed, closeOk, sealAttempted, sealedOk;
        private string closedHash;
        private TimestampMatrixReport matrix;

        internal SessionTimestampEvidenceV1(object owner, SessionTimestampLifecycleV1 life,
            string folder, string probeUuid, string requestUuid, string evidenceOrigin)
        {
            Guard(owner!=null && life!=null && life.IsOwner(owner),"WRITER_OWNER_INVALID");
            Guard(evidenceOrigin=="SYNTHETIC" || evidenceOrigin=="OPERATOR_NATIVE_RUN_UNATTESTED","ORIGIN_INVALID");
            Guid p,r;
            Guard(Guid.TryParseExact(probeUuid,"D",out p) && p.ToString("D")==probeUuid,"PROBE_UUID_INVALID");
            Guard(Guid.TryParseExact(requestUuid,"D",out r) && r.ToString("D")==requestUuid && r!=p,"REQUEST_UUID_INVALID");
            hostOwner=owner; instanceOwner=this; lifecycle=life;
            origin=evidenceOrigin; probeId=probeUuid; requestId=requestUuid;
            directory=CheckedDirectory(folder);
            Guard(Directory.GetFileSystemEntries(directory).Length==0,"OUTPUT_NOT_EMPTY");
            try
            {
                stream=new FileStream(Path.Combine(directory,DiagnosticName),FileMode.CreateNew,
                    FileAccess.Write,FileShare.Read,4096,FileOptions.WriteThrough);
                runningHash=SHA256.Create();
                Write("EVIDENCE_STARTED",new { format="RAW_CLOCK_TEXT_PLUS_TICKS_AND_KIND",source_metadata_attestation="CALLER_SUPPLIED_NOT_INDEPENDENTLY_ATTESTED" });
            }
            catch
            {
                failed=true;
                if(stream!=null)stream.Dispose();
                if(runningHash!=null)runningHash.Dispose();
                closed=true;
                throw new EvidenceGuardException("OUTPUT_OPEN_FAILED");
            }
        }
        private static void Guard(bool condition,string id)
        { if(!condition)throw new EvidenceGuardException(id); }
        private void Owner(object owner)
        { Guard(Object.ReferenceEquals(this,instanceOwner) && Object.ReferenceEquals(owner,hostOwner),"WRITER_NOT_OWNER"); }
        internal bool Sealed { get { lock(sync) { return sealedOk; } } }
        private static string CheckedDirectory(string folder)
        {
            Guard(!String.IsNullOrWhiteSpace(folder) && Path.IsPathRooted(folder),"OUTPUT_PATH_INVALID");
            string full=Path.GetFullPath(folder), root=Path.GetPathRoot(full);
            Guard(!String.IsNullOrEmpty(root) && !root.StartsWith(@"\\",StringComparison.Ordinal),"OUTPUT_NOT_LOCAL");
            // Reject drive-relative and root-relative Windows paths; accept only resolved absolute input.
            Guard(String.Equals(full.TrimEnd(Path.DirectorySeparatorChar),folder.TrimEnd(Path.DirectorySeparatorChar),
                StringComparison.OrdinalIgnoreCase),"OUTPUT_PATH_NOT_CANONICAL");
            Guard(Directory.Exists(full) && new DriveInfo(root).DriveType==DriveType.Fixed,"OUTPUT_NOT_FIXED_DIRECTORY");
            for(var d=new DirectoryInfo(full);d!=null;d=d.Parent)
                Guard((d.Attributes&FileAttributes.ReparsePoint)==0,"OUTPUT_REPARSE_POINT");
            return full;
        }
        private void OwnFiles(bool afterSeal)
        {
            Guard(CheckedDirectory(directory)==directory,"OUTPUT_PATH_CHANGED");
            string[] paths=Directory.GetFileSystemEntries(directory);
            Guard(paths.Length==(afterSeal?2:1),"FOREIGN_OUTPUT_ENTRY");
            foreach(string path in paths)
            {
                string name=Path.GetFileName(path);
                Guard(name==DiagnosticName || (afterSeal && name==SealName),"FOREIGN_OUTPUT_ENTRY");
                Guard((File.GetAttributes(path)&(FileAttributes.ReparsePoint|FileAttributes.Directory))==0,"OUTPUT_ENTRY_INVALID");
            }
        }
        private static string Digest(byte[] data)
        { using(var h=SHA256.Create())return Hex(h.ComputeHash(data)); }
        private static string Hex(byte[] data)
        { return BitConverter.ToString(data).Replace("-","").ToLowerInvariant(); }
        internal static object Timestamp(DateTime? value)
        {
            if(!value.HasValue)return null;
            DateTime t=value.Value;
            return new { clock=t.ToString("yyyy-MM-ddTHH:mm:ss.fffffff",CultureInfo.InvariantCulture),ticks=t.Ticks,kind=t.Kind.ToString() };
        }
        private static object Control(QueryControl c)
        {
            return new { ordinal=c.Ordinal,case_id=c.CaseId,family=c.Family,iterator_id=c.IteratorId,
                reuse=c.Reuse,prerequisite=c.Prerequisite,source_index=c.SourceIndex,provenance=c.Provenance,
                reference_utc=Timestamp(c.ReferenceUtc),constructor_context=c.ConstructorContext,include_end_time=c.IncludeEndTime,
                raw_range=c.RawTicksWithinEndpointRange,range_interpretation=c.RangeInterpretation,
                raw=Timestamp(c.Time.Raw),query=Timestamp(c.Time.Query),variant=c.Time.Variant,method=c.Time.Method,
                source_zone_id=c.Time.SourceZoneId,source_offset_ticks=c.Time.SourceOffsetTicks,
                conversion_performed=c.Time.ConversionPerformed,kind_changed=c.Time.KindChanged,tick_delta=c.Time.TickDelta };
        }
        private static object Observation(TimestampCaseObservation o)
        {
            return new { case_id=o.Control.CaseId,outcome=o.Outcome,guard=o.GuardId,exception_type=o.ExceptionType,
                returned=o.Returned,begin=Timestamp(o.Begin),end=Timestamp(o.End),bounds_readable=o.BoundsReadable,
                bounds_valid=o.BoundsValid,constructor_attempts=o.ConstructorAttemptsAfter,call_attempts=o.CallAttemptsAfter };
        }
        private void Write(string stage,object payload)
        {
            Guard(!closed && stream!=null,"WRITER_CLOSED");
            var row=new { schema="arms.r53.evidence.record.v1",version=Version,classification="DIAGNOSTIC_ONLY",
                origin=origin,probe_uuid=probeId,request_uuid=requestId,sequence=records,stage=stage,
                native_provenance_attested=false,certification_evidence=false,runtime_admission=false,
                execution_authority=false,payload=payload };
            byte[] data=new UTF8Encoding(false,true).GetBytes(new JavaScriptSerializer().Serialize(row)+"\n");
            Guard(records<MaximumRecords && data.Length<=MaximumRecordBytes && bytes+data.Length<=MaximumBytes,"EVIDENCE_BUDGET_EXCEEDED");
            stream.Write(data,0,data.Length);stream.Flush(true);
            runningHash.TransformBlock(data,0,data.Length,data,0);records++;bytes+=data.Length;
        }
        private static bool SafeErrorName(string name)
        { return name=="InvalidOperationException" || name=="ArgumentException" || name=="NullReferenceException" || name=="OverflowException" || name=="OTHER"; }
        private static void ValidateMatrix(TimestampMatrixReport report)
        {
            int creates=0,calls=0,begins=0,ends=0;bool r0=false;
            string[] ids={"A_U","A_LUTC","A_THUTC","B_U","B_LUTC","B_THUTC","C_U","C_LUTC","C_THUTC","R0","R1","N"};
            for(int i=0;i<12;i++)
            {
                var o=report.Observations[i];
                Guard(o!=null && o.Control!=null && o.Control.CaseId==ids[i],"OBSERVATION_ORDER_INVALID");
                bool readable=false,valid=false;string guard="NONE";
                if(i==10 && !r0)
                {
                    Guard(o.Outcome=="SKIPPED" && o.ExceptionType=="NONE" && !o.Returned.HasValue && !o.Begin.HasValue && !o.End.HasValue,"SKIP_INVALID");
                    guard="R0_TRUE_READABLE_VALID_BOUNDS_NOT_MET";
                }
                else
                {
                    if(i!=10)creates++;
                    if(o.Outcome=="CONSTRUCTOR_EXCEPTION")
                        Guard(i!=10 && !o.Returned.HasValue && !o.Begin.HasValue && !o.End.HasValue && SafeErrorName(o.ExceptionType),"CONSTRUCTOR_OUTCOME_INVALID");
                    else
                    {
                        calls++;
                        if(o.Outcome=="RETURNED_FALSE" || o.Outcome=="ADVANCE_EXCEPTION")
                            Guard(o.Returned==(o.Outcome=="RETURNED_FALSE"?(bool?)false:null) && !o.Begin.HasValue && !o.End.HasValue &&
                                (o.Outcome=="RETURNED_FALSE"?o.ExceptionType=="NONE":SafeErrorName(o.ExceptionType)),"CALL_OUTCOME_INVALID");
                        else
                        {
                            Guard(o.Returned==true,"TRUE_OUTCOME_INVALID");begins++;
                            if(o.Outcome=="BEGIN_READ_EXCEPTION")
                                Guard(!o.Begin.HasValue && !o.End.HasValue && SafeErrorName(o.ExceptionType),"BEGIN_OUTCOME_INVALID");
                            else
                            {
                                Guard(o.Begin.HasValue,"BEGIN_MISSING");ends++;
                                if(o.Outcome=="END_READ_EXCEPTION")
                                    Guard(!o.End.HasValue && SafeErrorName(o.ExceptionType),"END_OUTCOME_INVALID");
                                else
                                {
                                    Guard(o.End.HasValue && o.ExceptionType=="NONE","BOUNDS_MISSING");readable=true;
                                    valid=o.Begin.Value.Kind==o.End.Value.Kind && o.Begin.Value.Ticks<o.End.Value.Ticks;
                                    Guard(o.Outcome==(valid?"RETURNED_TRUE":"BOUNDS_INVALID"),"BOUNDS_OUTCOME_INVALID");
                                    if(!valid)guard=o.Begin.Value.Kind!=o.End.Value.Kind?"BOUNDS_KIND_MISMATCH":"BOUNDS_NON_POSITIVE";
                                }
                            }
                        }
                    }
                }
                Guard(o.GuardId==guard && o.BoundsReadable==readable && o.BoundsValid==valid &&
                    o.ConstructorAttemptsAfter==creates && o.CallAttemptsAfter==calls,"OBSERVATION_COUNTERS_INVALID");
                if(i==9)r0=o.Returned==true && readable && valid;
            }
            Guard(report.ConstructorAttempts==creates && report.CallAttempts==calls && report.BeginReadAttempts==begins && report.EndReadAttempts==ends,"MATRIX_TOTALS_INVALID");
        }
        internal void Prepare(object owner,TimestampQueryPlan plan,TimestampMatrixReport report)
        {
            Owner(owner);
            lock(sync)
            {
                Guard(!sealedOk && !closed,"WRITER_CLOSED");
                try
                {
                    Guard(!failed && !prepared,"PREPARATION_REPEATED");
                    Guard(plan!=null && report!=null && report.MatrixCompleted && report.StopGuard=="NONE","MATRIX_NOT_COMPLETE");
                    Guard(plan.Cases.Count==12 && report.Observations.Count==12,"CASE_COUNT_INVALID");
                    for(int i=0;i<12;i++)
                        Guard(Object.ReferenceEquals(plan.Cases[i],report.Observations[i].Control),"MATRIX_PLAN_IDENTITY_MISMATCH");
                    Guard(report.ConstructorAttempts<=11 && report.CallAttempts<=12 && report.BeginReadAttempts<=12 && report.EndReadAttempts<=12,"MATRIX_BUDGET_INVALID");
                    ValidateMatrix(report);
                    OwnFiles(false);
                    var controls=new List<object>();foreach(var c in plan.Cases)controls.Add(Control(c));
                    Write("PLAN_PREPARED",new { returned_rows=plan.ReturnedRows,raw_first=Timestamp(plan.RawFirst),raw_last=Timestamp(plan.RawLast),
                        snapshot_sha256=plan.SnapshotSha256,template_sha256=plan.TemplateSha256,source_zone_id=plan.SourceZoneId,
                        template_calendar_attested=false,maximum_calls=12,maximum_iterators=11,cases=controls });
                    foreach(var o in report.Observations)Write("CASE_RESULT",Observation(o));
                    Write("EVIDENCE_PREPARED",new { matrix_completed=true,stop_guard=report.StopGuard,
                        constructor_attempts=report.ConstructorAttempts,call_attempts=report.CallAttempts,
                        begin_read_attempts=report.BeginReadAttempts,end_read_attempts=report.EndReadAttempts });
                    matrix=report;prepared=true;
                }
                catch(Exception error)
                {
                    failed=true;
                    try { var e=error as EvidenceGuardException;Write("EVIDENCE_FAILED",new { guard=e==null?"EVIDENCE_PREPARE_FAILED":e.GuardId }); } catch { }
                    throw new EvidenceGuardException("EVIDENCE_PREPARATION_FAILED");
                }
            }
        }
        public void Dispose()
        {
            // A shallow clone is not the writer owner and must never close the original.
            if(!Object.ReferenceEquals(this,instanceOwner))return;
            lock(sync)
            {
                if(closed)return;
                closed=true;bool ok=false;
                try
                {
                    stream.Flush(true);runningHash.TransformFinalBlock(new byte[0],0,0);
                    closedHash=Hex(runningHash.Hash);ok=true;
                }
                finally
                {
                    try { if(stream!=null)stream.Dispose(); }
                    catch { ok=false;failed=true;throw new EvidenceGuardException("WRITER_DISPOSE_FAILED"); }
                    finally { stream=null;if(runningHash!=null)runningHash.Dispose();runningHash=null;closeOk=ok; }
                }
            }
        }
        internal void PublishSeal(object owner)
        {
            Owner(owner);
            lock(sync)
            {
                Guard(!sealAttempted && !sealedOk,"SEAL_ALREADY_ATTEMPTED");
                sealAttempted=true;
                try
                {
                    Guard(!failed && prepared && closed && closeOk,"WRITER_NOT_READY_FOR_SEAL");
                    var s=lifecycle.Inspect(owner);
                    Guard(s.ReadyForSeal && s.ResourcesReleased && s.RequestClosed && s.WriterClosed && s.SubmitReturned,
                        "LIFECYCLE_NOT_READY_FOR_SEAL");
                    Guard(s.Status=="READY_FOR_SEAL_NOT_SEALED" && s.StopGuard=="NONE" && s.ExceptionType=="NONE" &&
                        s.DuplicateCallbacks==0 && s.WriterFactoryAttempts==1 && s.RequestFactoryAttempts==1 && s.SubmitAttempts==1 &&
                        s.ProcessAttempts==1 && s.PreparationAttempts==1 && s.RequestDisposeAttempts==1 && s.WriterDisposeAttempts==1,
                        "LIFECYCLE_COUNTERS_INVALID");
                    Guard(Object.ReferenceEquals(s.Matrix,matrix),"LIFECYCLE_MATRIX_IDENTITY_MISMATCH");
                    OwnFiles(false);
                    string path=Path.Combine(directory,DiagnosticName);
                    Guard(new FileInfo(path).Length==bytes && bytes<=MaximumBytes,"EVIDENCE_SIZE_CHANGED");
                    byte[] content=File.ReadAllBytes(path);
                    Guard(content.Length==bytes && Digest(content)==closedHash,"EVIDENCE_BYTES_CHANGED");
                    Guard(records==15,"EVIDENCE_RECORD_COUNT_INVALID");
                    var seal=new { schema="arms.r53.evidence.seal.v1",version=Version,classification="DIAGNOSTIC_ONLY",origin=origin,
                        probe_uuid=probeId,request_uuid=requestId,sha256=closedHash,bytes=bytes,records=records,
                        diagnostic_complete=true,writer_closed=true,native_provenance_attested=false,certification_evidence=false,
                        runtime_admission=false,execution_authority=false,
                        lifecycle=new { status=s.Status,stop_guard=s.StopGuard,exception_type=s.ExceptionType,
                            writer_factory_attempts=s.WriterFactoryAttempts,request_factory_attempts=s.RequestFactoryAttempts,
                            submit_attempts=s.SubmitAttempts,process_attempts=s.ProcessAttempts,preparation_attempts=s.PreparationAttempts,
                            request_dispose_attempts=s.RequestDisposeAttempts,writer_dispose_attempts=s.WriterDisposeAttempts,
                            duplicate_callbacks=s.DuplicateCallbacks,submit_returned=s.SubmitReturned,request_closed=s.RequestClosed,
                            writer_closed=s.WriterClosed,resources_released=s.ResourcesReleased,ready_for_seal=s.ReadyForSeal } };
                    byte[] data=new UTF8Encoding(false,true).GetBytes(new JavaScriptSerializer().Serialize(seal));
                    Guard(data.Length<=4096,"SEAL_SIZE_EXCEEDED");
                    string temporary=Path.Combine(directory,"session-timestamp-evidence.done.tmp");
                    using(var f=new FileStream(temporary,FileMode.CreateNew,FileAccess.Write,FileShare.None,4096,FileOptions.WriteThrough))
                    { f.Write(data,0,data.Length);f.Flush(true); }
                    // Same directory, no overwrite. The private temporary file remains on any failure.
                    File.Move(temporary,Path.Combine(directory,SealName));sealedOk=true;
                }
                catch { failed=true;throw new EvidenceGuardException("SEAL_NOT_PUBLISHED"); }
            }
        }
    }
}
