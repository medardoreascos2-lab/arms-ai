// R5.3-G: bind exact F context bytes and the D matrix/seal in one envelope.
// Not an Indicator; no automatic request, SDK invocation, normalization or execution.
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Security.Cryptography;
using System.Text;
using System.Web.Script.Serialization;

namespace Arms.AI.Diagnostics.R53
{
    internal sealed class ContextEnvelopeGuardException : InvalidOperationException
    {
        internal string GuardId { get; private set; }
        internal ContextEnvelopeGuardException(string guard) : base(guard) { GuardId=guard; }
    }

    internal sealed class SessionTimestampContextEnvelopeV1 : IDisposable
    {
        internal const string Version="R5.3-G/context-envelope/1";
        internal const string ContextName="session-timestamp-context.json";
        internal const string SealName="session-timestamp-context.done.json";
        internal const string MatrixDirectory="matrix";
        internal const int MaximumContextBytes=131072,MaximumTotalBytes=262144,MaximumSealBytes=4096;
        private readonly SessionTimestampContextEnvelopeV1 instanceOwner;
        private readonly object hostOwner,sync=new object();
        private readonly SessionTimestampLifecycleV1 life;
        private readonly SessionTimestampNativeContextV1 context;
        private readonly string folder,probeId,requestId,origin;
        private SessionTimestampEvidenceV1 matrixWriter;
        private TimestampQueryPlan plan;
        private TimestampMatrixReport report;
        private string contextHash;
        private int contextBytes;
        private bool prepared,closed,closeOk,failed,sealAttempted,sealedOk;

        internal SessionTimestampContextEnvelopeV1(object owner,SessionTimestampLifecycleV1 lifecycle,
            SessionTimestampNativeContextV1 loadedContext,string directory,string probeUuid,string requestUuid,string evidenceOrigin)
        {
            Guard(owner!=null && lifecycle!=null && lifecycle.IsOwner(owner) && loadedContext!=null,"ENVELOPE_DEPENDENCIES");
            instanceOwner=this;hostOwner=owner;life=lifecycle;context=loadedContext;
            context.CheckEnvironment(owner);
            Guid p,r;
            Guard(Guid.TryParseExact(probeUuid,"D",out p) && p.ToString("D")==probeUuid &&
                Guid.TryParseExact(requestUuid,"D",out r) && r.ToString("D")==requestUuid && p!=r,"ENVELOPE_IDENTITIES");
            Guard(evidenceOrigin=="SYNTHETIC" || evidenceOrigin=="OPERATOR_NATIVE_RUN_UNATTESTED","ENVELOPE_ORIGIN");
            probeId=probeUuid;requestId=requestUuid;origin=evidenceOrigin;
            folder=CheckedDirectory(directory);
            Guard(Directory.GetFileSystemEntries(folder).Length==0,"ENVELOPE_DIRECTORY_NOT_EMPTY");
            string child=Path.Combine(folder,MatrixDirectory);
            try
            {
                Guard(!Directory.Exists(child) && !File.Exists(child),"MATRIX_DIRECTORY_EXISTS");
                Directory.CreateDirectory(child);
                matrixWriter=new SessionTimestampEvidenceV1(owner,life,child,probeId,requestId,origin);
                OwnFiles(false,false);
            }
            catch
            {
                failed=true;
                if(matrixWriter!=null)try { matrixWriter.Dispose(); }catch { }
                throw new ContextEnvelopeGuardException("ENVELOPE_OPEN_FAILED");
            }
        }
        private static void Guard(bool ok,string id) { if(!ok)throw new ContextEnvelopeGuardException(id); }
        private void Owner(object owner)
        { Guard(Object.ReferenceEquals(this,instanceOwner) && Object.ReferenceEquals(hostOwner,owner),"ENVELOPE_NOT_OWNER"); }
        internal bool Sealed { get { Owner(hostOwner);lock(sync)return sealedOk; } }
        private static string Hash(byte[] bytes)
        { using(var h=SHA256.Create())return BitConverter.ToString(h.ComputeHash(bytes)).Replace("-","").ToLowerInvariant(); }
        private static byte[] Utf8(string text) { return new UTF8Encoding(false,true).GetBytes(text); }
        private static string CheckedDirectory(string path)
        {
            Guard(!String.IsNullOrWhiteSpace(path) && Path.IsPathRooted(path),"ENVELOPE_PATH_INVALID");
            string full=Path.GetFullPath(path),root=Path.GetPathRoot(full);
            Guard(!String.IsNullOrEmpty(root) && !root.StartsWith(@"\\",StringComparison.Ordinal),"ENVELOPE_NOT_LOCAL");
            Guard(String.Equals(full.TrimEnd(Path.DirectorySeparatorChar),path.TrimEnd(Path.DirectorySeparatorChar),StringComparison.OrdinalIgnoreCase),"ENVELOPE_PATH_NONCANONICAL");
            Guard(Directory.Exists(full) && new DriveInfo(root).DriveType==DriveType.Fixed,"ENVELOPE_NOT_FIXED_DIRECTORY");
            for(var d=new DirectoryInfo(full);d!=null;d=d.Parent)
                Guard((d.Attributes&FileAttributes.ReparsePoint)==0,"ENVELOPE_REPARSE_POINT");
            return full;
        }
        private void OwnFiles(bool hasContext,bool hasEnvelope)
        {
            Guard(CheckedDirectory(folder)==folder,"ENVELOPE_DIRECTORY_CHANGED");
            string[] entries=Directory.GetFileSystemEntries(folder);
            Guard(entries.Length==1+(hasContext?1:0)+(hasEnvelope?1:0),"ENVELOPE_FOREIGN_ENTRY");
            foreach(string path in entries)
            {
                string name=Path.GetFileName(path);var attr=File.GetAttributes(path);
                Guard((attr&FileAttributes.ReparsePoint)==0,"ENVELOPE_ENTRY_REPARSE_POINT");
                if(name==MatrixDirectory)
                    Guard((attr&FileAttributes.Directory)!=0,"MATRIX_NOT_DIRECTORY");
                else
                    Guard(((hasContext && name==ContextName)||(hasEnvelope && name==SealName)) &&
                        (attr&FileAttributes.Directory)==0,"ENVELOPE_FOREIGN_ENTRY");
            }
        }
        private void MatrixFiles(bool hasSeal)
        {
            string child=Path.Combine(folder,MatrixDirectory);CheckedDirectory(child);
            var entries=Directory.GetFileSystemEntries(child);
            Guard(entries.Length==(hasSeal?2:1),"MATRIX_FOREIGN_ENTRY");
            foreach(var path in entries)
                Guard((Path.GetFileName(path)==SessionTimestampEvidenceV1.DiagnosticName ||
                    (hasSeal && Path.GetFileName(path)==SessionTimestampEvidenceV1.SealName)) &&
                    (File.GetAttributes(path)&(FileAttributes.Directory|FileAttributes.ReparsePoint))==0,"MATRIX_ENTRY_INVALID");
        }
        private static Dictionary<string,object> Map(object value)
        { var d=value as Dictionary<string,object>;Guard(d!=null,"CONTEXT_OBJECT_INVALID");return d; }
        private static long Integer(object value)
        { Guard(value is int || value is long,"CONTEXT_INTEGER_INVALID");return Convert.ToInt64(value,CultureInfo.InvariantCulture); }
        private static void TimestampMatches(object value,DateTime expected)
        {
            var d=Map(value);
            Guard(Integer(d["ticks"])==expected.Ticks && (string)d["kind"]==expected.Kind.ToString() &&
                (string)d["clock"]==expected.ToString("yyyy-MM-ddTHH:mm:ss.fffffff",CultureInfo.InvariantCulture),"CONTEXT_TIMESTAMP_BINDING");
        }
        private static void BindText(string text,TimestampQueryPlan candidate)
        {
            var d=Map(new JavaScriptSerializer { MaxJsonLength=MaximumContextBytes }.DeserializeObject(text));
            Guard((string)d["schema"]=="arms.r53.loaded-context.v1" && (string)d["version"]==SessionTimestampNativeContextV1.Version,"CONTEXT_SCHEMA");
            Guard(Integer(d["source_index"])==0 && Integer(d["request_constructor_attempts"])==1,"CONTEXT_SOURCE_BINDING");
            TimestampMatches(d["source_timestamp"],candidate.RawFirst);
            var s=Map(d["snapshot"]);
            Guard(Integer(s["rows"])==candidate.ReturnedRows && (string)s["sha256"]==candidate.SnapshotSha256,"CONTEXT_SNAPSHOT_BINDING");
            TimestampMatches(s["first"],candidate.RawFirst);TimestampMatches(s["last"],candidate.RawLast);
            string calendar=(string)d["loaded_calendar_json"],configuration=(string)d["request_configuration_json"];
            Guard(Hash(Utf8(calendar))==(string)d["loaded_calendar_sha256"] && (string)d["loaded_calendar_sha256"]==candidate.TemplateSha256,"CONTEXT_CALENDAR_BINDING");
            Guard(Hash(Utf8(configuration))==(string)d["request_configuration_sha256"],"CONTEXT_CONFIGURATION_BINDING");
            Guard((string)Map(new JavaScriptSerializer().DeserializeObject(calendar))["zone_id"]==candidate.SourceZoneId,"CONTEXT_ZONE_BINDING");
        }
        internal void Prepare(object owner,TimestampQueryPlan candidate,TimestampMatrixReport result)
        {
            Owner(owner);
            lock(sync)
            {
                Guard(!prepared && !closed && !failed && !sealAttempted,"ENVELOPE_PREPARE_STATE");
                try
                {
                    Guard(candidate!=null && result!=null && candidate.Cases.Count==12 && result.Observations.Count==12,"ENVELOPE_PLAN_MISSING");
                    context.Revalidate(owner);
                    foreach(var control in candidate.Cases)context.Check(owner,"ENVELOPE_CONTROL_BINDING",control);
                    string captured=context.CapturedContext(owner);byte[] data=Utf8(captured);
                    Guard(data.Length>0 && data.Length<=MaximumContextBytes,"CONTEXT_BYTE_LIMIT");BindText(captured,candidate);
                    OwnFiles(false,false);MatrixFiles(false);
                    using(var f=new FileStream(Path.Combine(folder,ContextName),FileMode.CreateNew,FileAccess.Write,FileShare.None,4096,FileOptions.WriteThrough))
                    { f.Write(data,0,data.Length);f.Flush(true); }
                    contextHash=Hash(data);contextBytes=data.Length;
                    matrixWriter.Prepare(owner,candidate,result);
                    context.Revalidate(owner);Guard(context.CapturedContext(owner)==captured,"CAPTURED_CONTEXT_CHANGED");
                    OwnFiles(true,false);MatrixFiles(false);plan=candidate;report=result;prepared=true;
                }
                catch { failed=true;throw new ContextEnvelopeGuardException("ENVELOPE_PREPARATION_FAILED"); }
            }
        }
        public void Dispose()
        {
            if(!Object.ReferenceEquals(this,instanceOwner))return;
            lock(sync)
            {
                if(closed)return;closed=true;
                try { matrixWriter.Dispose();closeOk=true; }
                catch { failed=true;throw new ContextEnvelopeGuardException("ENVELOPE_WRITER_CLOSE_FAILED"); }
            }
        }
        private static FileStream OpenRead(string path,int maximum)
        {
            Guard((File.GetAttributes(path)&(FileAttributes.Directory|FileAttributes.ReparsePoint))==0,"BOUND_FILE_INVALID");
            var f=new FileStream(path,FileMode.Open,FileAccess.Read,FileShare.Read);
            if(f.Length<=0 || f.Length>maximum) { f.Dispose();throw new ContextEnvelopeGuardException("BOUND_FILE_SIZE"); }
            return f;
        }
        private static byte[] Read(FileStream f)
        {
            byte[] data=new byte[(int)f.Length];int offset=0;
            while(offset<data.Length) { int n=f.Read(data,offset,data.Length-offset);Guard(n>0,"BOUND_FILE_TRUNCATED");offset+=n; }
            Guard(f.ReadByte()==-1 && f.Length==data.Length,"BOUND_FILE_CHANGED");return data;
        }
        internal void PublishSeal(object owner)
        {
            Owner(owner);
            lock(sync)
            {
                Guard(!sealAttempted && !sealedOk,"ENVELOPE_SEAL_ALREADY_ATTEMPTED");sealAttempted=true;
                try
                {
                    Guard(prepared && closed && closeOk && !failed,"ENVELOPE_NOT_READY");
                    var state=life.Inspect(owner);
                    Guard(state.ReadyForSeal && state.ResourcesReleased && state.RequestClosed && state.WriterClosed &&
                        Object.ReferenceEquals(state.Matrix,report),"ENVELOPE_LIFECYCLE_NOT_READY");
                    // Environment only: never read request.Bars after C/E have disposed it.
                    context.CheckEnvironment(owner);OwnFiles(true,false);MatrixFiles(false);
                    string matrixPath=Path.Combine(folder,MatrixDirectory);
                    using(var cf=OpenRead(Path.Combine(folder,ContextName),MaximumContextBytes))
                    {
                        byte[] cb=Read(cf);
                        Guard(cb.Length==contextBytes && Hash(cb)==contextHash,"CONTEXT_BYTES_CHANGED");
                        Guard(Hash(Utf8(context.CapturedContext(owner)))==contextHash,"CONTEXT_IDENTITY_CHANGED");
                        matrixWriter.PublishSeal(owner);Guard(matrixWriter.Sealed,"MATRIX_NOT_SEALED");MatrixFiles(true);
                        using(var mf=OpenRead(Path.Combine(matrixPath,SessionTimestampEvidenceV1.DiagnosticName),MaximumTotalBytes))
                        using(var sf=OpenRead(Path.Combine(matrixPath,SessionTimestampEvidenceV1.SealName),MaximumSealBytes))
                        {
                            byte[] mb=Read(mf),sb=Read(sf);string mh=Hash(mb),sh=Hash(sb);
                            var inner=Map(new JavaScriptSerializer().DeserializeObject(new UTF8Encoding(false,true).GetString(sb)));
                            Guard((string)inner["probe_uuid"]==probeId && (string)inner["request_uuid"]==requestId &&
                                (string)inner["origin"]==origin && (string)inner["sha256"]==mh && Integer(inner["bytes"])==mb.Length &&
                                Integer(inner["records"])==15,"MATRIX_SEAL_BINDING");
                            var seal=new { schema="arms.r53.context-envelope.seal.v1",version=Version,classification="DIAGNOSTIC_ONLY",
                                probe_uuid=probeId,request_uuid=requestId,origin=origin,diagnostic_complete=true,writer_closed=true,
                                context_snapshot_sha256=plan.SnapshotSha256,context_template_sha256=plan.TemplateSha256,returned_rows=plan.ReturnedRows,
                                request_constructor_attempts=1,iterator_constructor_attempts=report.ConstructorAttempts,
                                getnextsession_attempts=report.CallAttempts,source_index=0,source_timestamp=SessionTimestampEvidenceV1.Timestamp(plan.RawFirst),
                                total_bound_bytes=cb.Length+mb.Length+sb.Length,
                                files=new[] {
                                    new { path=ContextName,bytes=cb.Length,sha256=contextHash },
                                    new { path=MatrixDirectory+"/"+SessionTimestampEvidenceV1.DiagnosticName,bytes=mb.Length,sha256=mh },
                                    new { path=MatrixDirectory+"/"+SessionTimestampEvidenceV1.SealName,bytes=sb.Length,sha256=sh } },
                                native_provenance_attested=false,certification_evidence=false,runtime_admission=false,execution_authority=false,
                                context_attestation="CAPTURED_VALUES_BOUND_NOT_PROVIDER_ATTESTATION" };
                            byte[] data=Utf8(new JavaScriptSerializer().Serialize(seal));
                            Guard(data.Length<=MaximumSealBytes && cb.Length+mb.Length+sb.Length+data.Length<=MaximumTotalBytes,"ENVELOPE_TOTAL_LIMIT");
                            context.CheckEnvironment(owner);OwnFiles(true,false);MatrixFiles(true);
                            string temporary=Path.Combine(folder,"session-timestamp-context.done.tmp");
                            using(var f=new FileStream(temporary,FileMode.CreateNew,FileAccess.Write,FileShare.None,4096,FileOptions.WriteThrough))
                            { f.Write(data,0,data.Length);f.Flush(true); }
                            File.Move(temporary,Path.Combine(folder,SealName));sealedOk=true;
                        }
                    }
                }
                catch { failed=true;throw new ContextEnvelopeGuardException("CONTEXT_ENVELOPE_NOT_PUBLISHED"); }
            }
        }
    }
}
