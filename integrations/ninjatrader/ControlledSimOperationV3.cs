// Durable operation model consumed only by the existing Account bridge.
// No NinjaTrader SDK, account discovery, network, or ambient execution authority.
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;

namespace Arms.NativeSim
{
    public sealed class ControlledSnapshotV3
    {
        public string Account, Provider, Instrument, RiskVersion;
        public long Generation, ObservedUs;
        public bool Connected;
        public int PositionQuantity;
        public string PositionSide;
        public string[] ActiveOrderNames;
        public Dictionary<string,string> AccountClaims;
    }

    public sealed class ControlledOrderV3
    {
        public string Role, Name, Instrument, Action, Type, Oco;
        public int Quantity;
        public decimal Price;
    }

    // Any future SDK implementation belongs exclusively to the existing Account
    // bridge. Only recording doubles implement this interface in this package.
    public interface IControlledAccountV3
    {
        ControlledSnapshotV3 Snapshot();
        object Create(ControlledOrderV3 order);
        void Submit(object order);
        void Cancel(string[] names);
    }

    public sealed class ControlledAdmissionV3
    {
        internal static readonly string[] AccountFields = ("backend_account_id execution_domain risk_profile_id risk_profile_digest " +
            "ledger_id journal_account_id instrument_authority_id binding_digest").Split(' ');
        internal readonly Dictionary<string, string> Values;
        public readonly string Digest;
        private ControlledAdmissionV3(Dictionary<string,string> values, string digest)
        { Values = values; Digest = digest; }
        public string this[string key] { get { return Values[key]; } }
        public long Number(string key) { return long.Parse(this[key], CultureInfo.InvariantCulture); }
        public decimal Price(string key) { return decimal.Parse(this[key], NumberStyles.Float, CultureInfo.InvariantCulture); }
        internal static string Hex(byte[] bytes)
        { return BitConverter.ToString(bytes).Replace("-", "").ToLowerInvariant(); }
        internal static string Mac(byte[] key, byte[] bytes)
        { using(var mac = new HMACSHA256(key)) return Hex(mac.ComputeHash(bytes)); }
        internal static bool Equal(string a, string b)
        {
            if(a == null || b == null || a.Length != b.Length) return false;
            int difference = 0;
            for(int i=0;i<a.Length;i++) difference |= a[i] ^ b[i];
            return difference == 0;
        }
        private static readonly string[] Fields = (
            "admission_id signal_id plan_id operation_id command_id client_order_id approval_id activation_id " +
            "risk_approval_id risk_version quote_id runtime_id policy_version account provider instrument " +
            "runtime_generation side quantity stop_price target_price entry_price point_value risk_ceiling " +
            "signal_us quote_us runtime_us issued_us expires_us risk_expires_us max_signal_age_us " +
            "max_quote_age_us max_runtime_age_us protection_timeout_us recovery_timeout_us " +
            "risk_approval probability_approval confluence_approval news_approval market_approval rr_approval stop_approval"
        ).Split(' ').Concat(AccountFields).ToArray();

        public static ControlledAdmissionV3 Read(byte[] wire, byte[] trustedKey)
        {
            if(trustedKey == null || trustedKey.Length < 32 || wire == null || wire.Length > 32768)
                throw new InvalidDataException("Configured admission authority required.");
            if(wire.Any(b => b > 126 || (b < 32 && b != 9 && b != 10)))
                throw new InvalidDataException("Invalid admission encoding.");
            string text = Encoding.ASCII.GetString(wire);
            string[] header = text.Split(new[]{'\n'}, 4);
            if(header.Length != 4 || header[0] != "ARMS_SIM_ADMISSION_V3")
                throw new InvalidDataException("Invalid admission schema.");
            byte[] payload = Encoding.ASCII.GetBytes(header[3]);
            string digest;
            using(var sha=SHA256.Create()) digest=Hex(sha.ComputeHash(payload));
            byte[] domain=Encoding.ASCII.GetBytes("arms.native.admission.v3\0");
            if(!Equal(digest,header[1]) || !Equal(Mac(trustedKey,domain.Concat(payload).ToArray()),header[2]))
                throw new InvalidDataException("Unverifiable admission authority/content.");
            var fields=new Dictionary<string,string>(StringComparer.Ordinal);
            string[] rows=header[3].Split('\n');
            if(rows[rows.Length-1] != "") throw new InvalidDataException("Noncanonical admission.");
            foreach(string row in rows.Take(rows.Length-1))
            {
                string[] pair=row.Split('\t');
                if(pair.Length!=2 || pair[1].Length==0 || fields.ContainsKey(pair[0]))
                    throw new InvalidDataException("Duplicate/invalid admission field.");
                fields.Add(pair[0],pair[1]);
            }
            if(!new HashSet<string>(Fields).SetEquals(fields.Keys) ||
                string.Concat(fields.OrderBy(p=>p.Key,StringComparer.Ordinal).Select(p=>p.Key+"\t"+p.Value+"\n")) != header[3])
                throw new InvalidDataException("Noncanonical admission fields.");
            return new ControlledAdmissionV3(fields,digest);
        }

        public void Validate(long now, ControlledSnapshotV3 snapshot, string configuredInstrument)
        {
            if(snapshot==null || snapshot.AccountClaims==null || this["execution_domain"]!="SIM_NATIVE")
                throw new InvalidDataException("Explicit native account authority required.");
            foreach(string field in AccountFields)
            {
                string expected;
                if(!snapshot.AccountClaims.TryGetValue(field,out expected) || expected!=this[field])
                    throw new InvalidDataException("Native backend account/risk authority mismatch.");
            }
            if(snapshot == null || snapshot.ActiveOrderNames == null || !snapshot.Connected ||
                this["account"]!="Sim101" || snapshot.Account!="Sim101" || this["provider"]!="Simulator" ||
                snapshot.Provider!="Simulator" || this["instrument"]!=configuredInstrument ||
                snapshot.Instrument!=configuredInstrument || this["runtime_generation"]!=snapshot.Generation.ToString(CultureInfo.InvariantCulture) ||
                snapshot.Generation<1 || this["risk_version"]!=snapshot.RiskVersion || this["quantity"]!="1" ||
                (this["side"]!="BUY" && this["side"]!="SELL") || this["operation_id"]!=this["client_order_id"] ||
                snapshot.PositionQuantity!=0 || snapshot.ActiveOrderNames.Length!=0)
                throw new InvalidDataException("Native admission binding/preflight rejected.");
            foreach(string key in Fields.Where(k=>k.EndsWith("_id") || k.EndsWith("_version")))
                if(!System.Text.RegularExpressions.Regex.IsMatch(this[key],@"\A[A-Za-z0-9_.-]{1,100}\z"))
                    throw new InvalidDataException("Invalid admission identity.");
            foreach(string gate in new[]{"risk","probability","confluence","news","market","rr","stop"})
                if(this[gate+"_approval"]!="APPROVED") throw new InvalidDataException("Admission gate rejected.");
            foreach(string key in Fields.Where(k=>k.EndsWith("_us")))
                if(!System.Text.RegularExpressions.Regex.IsMatch(this[key],@"\A[1-9][0-9]{0,17}\z"))
                    throw new InvalidDataException("Invalid admission time.");
            if(now<Number("issued_us") || now>=Number("expires_us") || now>=Number("risk_expires_us") ||
                Number("max_runtime_age_us")>15000000 || snapshot.ObservedUs>now ||
                now-snapshot.ObservedUs>Number("max_runtime_age_us"))
                throw new InvalidDataException("Expired/future admission or runtime.");
            foreach(string kind in new[]{"signal","quote","runtime"})
            {
                long observed=Number(kind+"_us"), age=Number("max_"+kind+"_age_us");
                if(now<observed || now-observed>age || Number("expires_us")>checked(observed+age))
                    throw new InvalidDataException("Stale/future admission evidence.");
            }
            decimal stop=Price("stop_price"), target=Price("target_price"), entry=Price("entry_price");
            if(stop<=0 || target<=0 || entry<=0 || Price("point_value")<=0 || Price("risk_ceiling")<=0 ||
                !(this["side"]=="BUY" ? stop<entry && entry<target : target<entry && entry<stop) ||
                Math.Abs(entry-stop)*Price("point_value")>Price("risk_ceiling"))
                throw new InvalidDataException("Invalid approved prices/risk.");
        }
    }

    public sealed class ControlledOperationV3 : IDisposable
    {
        private readonly ControlledAdmissionV3 admission;
        private readonly IControlledAccountV3 account;
        private readonly Func<long> clock;
        private readonly byte[] key;
        private readonly string directory, instrument;
        private readonly FileStream writer;
        private readonly Dictionary<string,string> state = new Dictionary<string,string>(StringComparer.Ordinal);
        private readonly object sync = new object();
        private int generation;
        private bool faulted;
        public Action<string> AfterPersist; // Offline crash injection; production leaves null.
        public string Status { get { lock(sync) return Get("status"); } }
        public bool EntriesBlocked { get { lock(sync) return Get("consumed")=="1" || faulted; } }
        private string Get(string name) { string value; return state.TryGetValue(name,out value)?value:""; }
        private long Now { get { return clock(); } }
        private string Prefix { get { return "a3."+admission.Digest.Substring(0,32); } }
        public string OrderName(string role)
        {
            string suffix=role=="ENTRY"?"E":role=="PROTECTIVE_STOP"?"S":role=="PROFIT_TARGET"?"T":role=="RECOVERY_CLOSE"?"R":null;
            if(suffix==null) throw new InvalidDataException("Unknown controlled order role.");
            return Prefix+"."+suffix;
        }
        public string RoleForName(string name)
        {
            foreach(string role in new[]{"ENTRY","PROTECTIVE_STOP","PROFIT_TARGET","RECOVERY_CLOSE"})
                if(OrderName(role)==name) return role;
            return null;
        }
        public void UnassignedEvidence()
        { lock(sync) { Recover("RECONCILIATION_REQUIRED"); } }
        public bool HasExecution(string executionId)
        { lock(sync) { return Get("execution."+executionId)!=""; } }
        private static string BaselineKey(string id)
        { using(var sha=SHA256.Create()) return "baseline_execution."+ControlledAdmissionV3.Hex(sha.ComputeHash(Encoding.UTF8.GetBytes(id))); }
        public void RecordExecutionBaseline(IEnumerable<string> ids)
        {
            lock(sync)
            {
                if(Get("consumed")=="1" || Get("status")!="ADMITTED" || Get("baseline_recorded")=="1")
                    throw new InvalidDataException("Execution baseline cannot change after admission.");
                foreach(string id in ids)
                { if(string.IsNullOrEmpty(id)) throw new InvalidDataException("Missing baseline execution identity."); state[BaselineKey(id)]=id; }
                state["baseline_recorded"]="1"; Save("EXECUTION_BASELINE");
            }
        }
        public bool IsBaselineExecution(string id)
        { lock(sync) { return !string.IsNullOrEmpty(id) && Get(BaselineKey(id))==id; } }
        public bool MatchesOrderIdentity(string name, string nativeId)
        { lock(sync) { string role=RoleForName(name); return role!=null && !string.IsNullOrEmpty(nativeId) && Get("order_id."+role)==nativeId; } }
        public void BindCreatedOrder(string role, string nativeId)
        {
            lock(sync)
            {
                OrderName(role);
                if(Get("create."+role)!="1" || string.IsNullOrEmpty(nativeId) ||
                    (Get("order_id."+role)!="" && Get("order_id."+role)!=nativeId))
                    throw new InvalidDataException("Unverifiable created native identity.");
                state["order_id."+role]=nativeId; Save("NATIVE_ORDER_BOUND");
            }
        }
        public ControlledOperationV3(ControlledAdmissionV3 admission, IControlledAccountV3 account,
            Func<long> clock, byte[] trustedKey, string directory, string instrument)
        {
            if(admission==null || account==null || clock==null || trustedKey==null || trustedKey.Length<32 ||
                !Path.IsPathRooted(directory) || !Directory.Exists(directory) || string.IsNullOrWhiteSpace(instrument))
                throw new InvalidDataException("Controlled operation configuration missing.");
            this.admission=admission; this.account=account; this.clock=clock;
            key=(byte[])trustedKey.Clone(); this.directory=directory; this.instrument=instrument;
            // One controlled account operation across hosts/processes. The same
            // configured directory must be used by every host for this profile.
            writer=new FileStream(Path.Combine(directory,"controlled-account.lock"),FileMode.OpenOrCreate,
                FileAccess.ReadWrite,FileShare.None);
            try
            {
                var records=Directory.GetFiles(directory,"*.state").OrderBy(p=>p,StringComparer.Ordinal).ToArray();
                if(records.Length>10000) throw new InvalidDataException("Native phase bound exceeded.");
                foreach(string path in records)
                {
                    generation++;
                    if(Path.GetFileName(path)!=generation.ToString("D8",CultureInfo.InvariantCulture)+".state")
                        throw new InvalidDataException("Native phase gap.");
                    ReadState(File.ReadAllBytes(path));
                    if(Get("admission_digest")!=admission.Digest || Get("generation")!=generation.ToString(CultureInfo.InvariantCulture))
                        throw new InvalidDataException("Native operation identity/version mismatch.");
                }
                if(generation==0)
                {
                    state["admission_digest"]=admission.Digest;
                    foreach(string field in ControlledAdmissionV3.AccountFields.Concat(new[]{"account","provider","instrument","runtime_generation","operation_id"}))
                        state[field]=admission[field];
                    state["status"]="ADMITTED";
                    Save("ADMITTED");
                }
                else if(Get("consumed")=="1" && Get("status")!="COMPLETED" && Get("status")!="RECOVERY_COMPLETE")
                {
                    if(Get("create.RECOVERY_CLOSE")=="1" && Get("exit_filled")!="1")
                    { state["status"]="RECONCILIATION_REQUIRED"; Save("RESTART_RECOVERY_UNKNOWN"); }
                    else if(Get("entry_filled")=="1" && Get("exit_filled")!="1")
                        Recover("PROTECTION_RECOVERY_REQUIRED");
                    else if(Get("submit.ENTRY")=="1" && Get("entry_filled")!="1")
                    { state["status"]="UNKNOWN_SUBMIT_OUTCOME"; Save("RESTART_UNKNOWN"); }
                    else if(Get("entry_filled")!="1")
                    { state["status"]="RECONCILIATION_REQUIRED"; Save("RESTART_CONSUMED"); }
                }
            }
            catch { writer.Dispose(); throw; }
        }
        private byte[] StateBytes()
        {
            return Encoding.UTF8.GetBytes(string.Concat(state.OrderBy(p=>p.Key,StringComparer.Ordinal)
                .Select(p=>p.Key+"\t"+Convert.ToBase64String(Encoding.UTF8.GetBytes(p.Value))+"\n")));
        }
        private void ReadState(byte[] bytes)
        {
            if(bytes.Length>1048576) throw new InvalidDataException("Native state too large.");
            string text=Encoding.UTF8.GetString(bytes); int split=text.IndexOf('\n');
            if(split!=64) throw new InvalidDataException("Incomplete native phase.");
            byte[] payload=Encoding.UTF8.GetBytes(text.Substring(split+1));
            if(!ControlledAdmissionV3.Equal(text.Substring(0,split),ControlledAdmissionV3.Mac(key,
                Encoding.UTF8.GetBytes("arms.native.phase.v3\0").Concat(payload).ToArray())))
                throw new InvalidDataException("Unverifiable native phase.");
            state.Clear();
            foreach(string row in text.Substring(split+1).Split('\n').Where(r=>r.Length>0))
            {
                string[] pair=row.Split('\t');
                if(pair.Length!=2 || state.ContainsKey(pair[0])) throw new InvalidDataException("Invalid native phase.");
                state.Add(pair[0],Encoding.UTF8.GetString(Convert.FromBase64String(pair[1])));
            }
        }
        private void Save(string phase)
        {
            if(faulted) throw new InvalidOperationException("Native persistence failed; recovery required.");
            state["phase"]=phase; state["generation"]=(generation+1).ToString(CultureInfo.InvariantCulture);
            state["recorded_us"]=Now.ToString(CultureInfo.InvariantCulture);
            byte[] payload=StateBytes();
            string signature=ControlledAdmissionV3.Mac(key,
                Encoding.UTF8.GetBytes("arms.native.phase.v3\0").Concat(payload).ToArray());
            byte[] wire=Encoding.ASCII.GetBytes(signature+"\n").Concat(payload).ToArray();
            try
            {
                using(var stream=new FileStream(Path.Combine(directory,(generation+1).ToString("D8",CultureInfo.InvariantCulture)+".state"),
                    FileMode.CreateNew,FileAccess.Write,FileShare.None))
                { stream.Write(wire,0,wire.Length); stream.Flush(true); }
                generation++;
            }
            catch { faulted=true; throw; }
            if(AfterPersist!=null) AfterPersist(phase);
        }
        private ControlledSnapshotV3 FreshSnapshot()
        {
            if(faulted) throw new InvalidOperationException("Native persistence fault.");
            var snapshot=account.Snapshot(); long now=Now;
            if(snapshot==null || snapshot.AccountClaims==null)
                throw new InvalidDataException("Native account authority unavailable.");
            foreach(string field in ControlledAdmissionV3.AccountFields)
            {
                string expected;
                if(!snapshot.AccountClaims.TryGetValue(field,out expected) || expected!=admission[field])
                    throw new InvalidDataException("Native account authority changed.");
            }
            if(snapshot==null || snapshot.Account!="Sim101" || snapshot.Provider!="Simulator" ||
                snapshot.Instrument!=instrument || snapshot.Generation!=admission.Number("runtime_generation") || snapshot.RiskVersion!=admission["risk_version"] ||
                snapshot.ActiveOrderNames==null || !snapshot.Connected ||
                snapshot.ObservedUs>now || now-snapshot.ObservedUs>admission.Number("max_runtime_age_us") ||
                snapshot.PositionQuantity<0 || snapshot.PositionQuantity>1 ||
                (snapshot.PositionQuantity==1 && snapshot.PositionSide!=admission["side"]))
                throw new InvalidDataException("Unverifiable native inventory; recovery required.");
            return snapshot;
        }
        public void Enter(string commandId, string commandDigest, string activationId,
            string activationDigest, bool activationPresent, bool activationConsumed,
            bool nativeSubmitEnabled, Action consumeActivation)
        {
            lock(sync)
            {
                if(EntriesBlocked || Get("status")!="ADMITTED" || !activationPresent || activationConsumed ||
                    commandId!=admission["command_id"] || commandDigest!=admission.Digest ||
                    activationId!=admission["activation_id"] || activationDigest!=admission.Digest || consumeActivation==null)
                    throw new InvalidDataException("Entry identity/activation rejected.");
                admission.Validate(Now,FreshSnapshot(),instrument);
                if(!nativeSubmitEnabled) throw new InvalidOperationException("Native SIM submit remains disabled.");
                // The durable operation fence wins even if the activation marker
                // write fails. Neither marker nor operation may ever be reused.
                try
                {
                    state["consumed"]="1"; Save("CONSUMED"); consumeActivation();
                    SubmitRole("ENTRY",0m);
                }
                catch
                {
                    if(!faulted)
                    {
                        state["status"]=Get("submit.ENTRY")=="1"?"UNKNOWN_SUBMIT_OUTCOME":"RECONCILIATION_REQUIRED";
                        Save("ENTRY_OUTCOME_UNCERTAIN");
                    }
                    throw;
                }
            }
        }
        private void SubmitRole(string role, decimal price)
        {
            if(Get("create."+role)=="1") throw new InvalidOperationException("Native role already attempted.");
            state["create."+role]="1"; Save(role=="ENTRY"?"CREATE_INTENT":role=="RECOVERY_CLOSE"?"RECOVERY_CREATE_INTENT":"CREATE_INTENT_"+role);
            var order=new ControlledOrderV3 { Role=role,Name=OrderName(role),Instrument=instrument,Quantity=1,
                Type=role=="ENTRY" || role=="RECOVERY_CLOSE"?"MARKET":role=="PROTECTIVE_STOP"?"STOP_MARKET":"LIMIT",
                Action=role=="ENTRY"?admission["side"]:admission["side"]=="BUY"?"SELL":"BUY_TO_COVER",
                Oco=role=="ENTRY" || role=="RECOVERY_CLOSE"?"":Prefix+".O",Price=price };
            object native=account.Create(order);
            if(native==null) throw new InvalidOperationException("Native creation returned no order.");
            state["created."+role]="1"; Save(role=="ENTRY"?"CREATED":role=="RECOVERY_CLOSE"?"RECOVERY_CREATED":"CREATED_"+role);
            state["submit."+role]="1"; Save(role=="ENTRY"?"SUBMIT_INTENT":role=="RECOVERY_CLOSE"?"RECOVERY_SUBMIT_INTENT":"SUBMIT_INTENT_"+role);
            account.Submit(native);
            Save(role=="ENTRY"?"SUBMIT_RETURNED":role=="RECOVERY_CLOSE"?"RECOVERY_SUBMIT_RETURNED":"SUBMIT_RETURNED_"+role);
        }
        private void Recover(string reason)
        {
            // A later Cancelled/Rejected label must not clear a contradictory
            // identity/ownership fence and silently re-enable automatic recovery.
            bool newFence=reason=="RECONCILIATION_REQUIRED" && Get("reconciliation_fence")!="1";
            if(reason=="RECONCILIATION_REQUIRED") state["reconciliation_fence"]="1";
            if(Get("reconciliation_fence")=="1") reason="RECONCILIATION_REQUIRED";
            if(!newFence && Get("status")==reason && Get("recovery_started_us")!="") return;
            state["status"]=reason;
            state["recovery_id"]=OrderName("RECOVERY_CLOSE");
            if(Get("recovery_started_us")=="") state["recovery_started_us"]=Now.ToString(CultureInfo.InvariantCulture);
            Save(reason);
        }
        public void Execution(string role, string executionId, decimal quantity, decimal price, string nativeOrderId)
        {
            lock(sync)
            {
                if(!new[]{"ENTRY","PROTECTIVE_STOP","PROFIT_TARGET","RECOVERY_CLOSE"}.Contains(role) || string.IsNullOrWhiteSpace(nativeOrderId) ||
                    string.IsNullOrWhiteSpace(executionId) ||
                    executionId.Any(c=>!char.IsLetterOrDigit(c) && c!='-' && c!='_' && c!='.'))
                { Recover("RECONCILIATION_REQUIRED"); return; }
                string id="execution."+executionId;
                string value=role+"|"+quantity.ToString(CultureInfo.InvariantCulture)+"|"+price.ToString(CultureInfo.InvariantCulture)+"|"+
                    Convert.ToBase64String(Encoding.UTF8.GetBytes(nativeOrderId));
                if(Get(id)!="")
                {
                    if(Get(id)!=value) Recover("RECONCILIATION_REQUIRED");
                    return;
                }
                if(Get("order_id."+role)!="" && Get("order_id."+role)!=nativeOrderId)
                { Recover("RECONCILIATION_REQUIRED"); return; }
                if(quantity!=1 || price<=0 || Get("submit."+role)!="1" ||
                    (role=="RECOVERY_CLOSE" && Get("recovery_id")!=OrderName(role)) ||
                    (role=="ENTRY" && Get("entry_filled")=="1") ||
                    (role!="ENTRY" && (Get("entry_filled")!="1" || Get("exit_filled")=="1")))
                { Recover("RECONCILIATION_REQUIRED"); return; }
                state[id]=value;
                state["order_id."+role]=nativeOrderId;
                if(role=="ENTRY")
                {
                    state["entry_filled"]="1"; state["entry_price"]=price.ToString(CultureInfo.InvariantCulture);
                    state["status"]="EXPOSED_AWAITING_PROTECTION";
                    state["protection_started_us"]=Now.ToString(CultureInfo.InvariantCulture);
                    Save("NATIVE_EVIDENCE");
                    decimal stop=admission.Price("stop_price"), target=admission.Price("target_price");
                    if(!(admission["side"]=="BUY"?stop<price && price<target:target<price && price<stop) ||
                        Math.Abs(price-stop)*admission.Price("point_value")>admission.Price("risk_ceiling"))
                    { Recover("ADVERSE_FILL_RECOVERY_REQUIRED"); return; }
                    try
                    {
                        FreshSnapshot();
                        Save("PROTECTION_PENDING");
                        SubmitRole("PROTECTIVE_STOP",stop);
                        if(Get("status")!="EXPOSED_AWAITING_PROTECTION") return;
                        SubmitRole("PROFIT_TARGET",target);
                    }
                    catch { Recover("PROTECTION_RECOVERY_REQUIRED"); throw; }
                }
                else
                {
                    state["exit_filled"]="1"; state["exit_price"]=price.ToString(CultureInfo.InvariantCulture);
                    state["status"]="EXIT_RECONCILIATION_REQUIRED";
                    Save(role=="RECOVERY_CLOSE"?"RECOVERY_NATIVE_EVIDENCE":"NATIVE_EVIDENCE");
                    Recover("EXIT_RECONCILIATION_REQUIRED");
                }
            }
        }
        public void OrderUpdate(string role, string status, string nativeOrderId, int filled = 0)
        {
            lock(sync)
            {
                OrderName(role);
                if(Get("submit."+role)!="1" || string.IsNullOrWhiteSpace(nativeOrderId)) { Recover("RECONCILIATION_REQUIRED"); return; }
                if(Get("order_id."+role)!="" && Get("order_id."+role)!=nativeOrderId)
                { Recover("RECONCILIATION_REQUIRED"); return; }
                state["order_id."+role]=nativeOrderId;
                if(filled<0 || filled>1) { Recover("RECONCILIATION_REQUIRED"); return; }
                string priorFilled=Get("order_filled."+role);
                if(filled==1 || status=="Filled") state["order_filled."+role]="1";
                if(!new[]{"Initialized","Submitted","Accepted","Working","PartFilled","Filled","Cancelled","Rejected","CancelPending","CancelSubmitted","ChangePending","ChangeSubmitted","TriggerPending"}.Contains(status))
                { Recover("RECONCILIATION_REQUIRED"); return; }
                // Do not regress terminal observations when callbacks are reordered.
                string previous=Get("order."+role);
                if(previous==status && priorFilled==Get("order_filled."+role)) return;
                if(previous=="Filled" || previous=="Cancelled" || previous=="Rejected")
                {
                    if(status==previous || new[]{"Initialized","Submitted","Accepted","Working","PartFilled"}.Contains(status))
                    { if(priorFilled!=Get("order_filled."+role)) Save("NATIVE_EVIDENCE"); return; }
                    Recover("RECONCILIATION_REQUIRED"); return;
                }
                state["order."+role]=status; Save("NATIVE_EVIDENCE");
                if(role!="ENTRY" && (status=="Rejected" || status=="Cancelled") && Get("exit_filled")!="1")
                    Recover("PROTECTION_RECOVERY_REQUIRED");
                else if(role=="ENTRY" && (status=="Rejected" || status=="Cancelled") && Get("entry_filled")!="1")
                { state["status"]="ENTRY_TERMINAL_RECONCILIATION_REQUIRED"; Save("NATIVE_EVIDENCE"); }
                else if(Get("status")=="EXPOSED_AWAITING_PROTECTION" &&
                    new[]{"Accepted","Working"}.Contains(Get("order.PROTECTIVE_STOP")) &&
                    new[]{"Accepted","Working"}.Contains(Get("order.PROFIT_TARGET")))
                { state["status"]="PROTECTED"; Save("PROTECTED"); }
            }
        }
        public void Tick()
        {
            lock(sync)
            {
                if(Get("status")=="EXPOSED_AWAITING_PROTECTION" &&
                    Now-long.Parse(Get("protection_started_us"),CultureInfo.InvariantCulture)>=admission.Number("protection_timeout_us"))
                    Recover("PROTECTION_RECOVERY_REQUIRED");
                if(Get("consumed")!="1" || Get("status")=="COMPLETED" || Get("status")=="RECOVERY_COMPLETE") return;
                ControlledSnapshotV3 snapshot;
                try { snapshot=FreshSnapshot(); }
                catch { Recover("PROTECTION_RECOVERY_REQUIRED"); return; }
                if(Get("status")=="PROTECTED" || Get("status")=="EXPOSED_AWAITING_PROTECTION") return;
                if(Get("status")=="RECONCILIATION_REQUIRED" || Get("reconciliation_fence")=="1") return;
                // Uncertain entry outcomes are evidence-only. They never authorize
                // another entry or a directional flatten on an unproven position.
                if(Get("entry_filled")!="1") return;
                if(Get("recovery_started_us")=="") Recover("PROTECTION_RECOVERY_REQUIRED");
                if(Now-long.Parse(Get("recovery_started_us"),CultureInfo.InvariantCulture)>=admission.Number("recovery_timeout_us"))
                { if(Get("status")!="RECOVERY_REQUIRED") {state["status"]="RECOVERY_REQUIRED"; Save("RECOVERY_TIMEOUT");} return; }
                if(snapshot.ActiveOrderNames.Any(n=>RoleForName(n)==null))
                { Recover("RECONCILIATION_REQUIRED"); return; }
                if(Get("create.RECOVERY_CLOSE")=="1" && Get("exit_filled")!="1") return;
                if(snapshot.ActiveOrderNames.Length>0)
                {
                    if(snapshot.ActiveOrderNames.Any(n=>RoleForName(n)!="PROTECTIVE_STOP" && RoleForName(n)!="PROFIT_TARGET"))
                    { Recover("RECONCILIATION_REQUIRED"); return; }
                    if(Get("cancel_intent")!="1")
                    {
                        state["cancel_intent"]="1";
                        state["cancel_names"]=string.Join("|",snapshot.ActiveOrderNames.OrderBy(n=>n,StringComparer.Ordinal));
                        Save("CANCEL_REQUESTED");
                        try { account.Cancel(snapshot.ActiveOrderNames); Save("CANCEL_RECONCILING"); }
                        catch { Recover("RECONCILIATION_REQUIRED"); throw; }
                    }
                    return;
                }
                // A fresh empty inventory alone is insufficient if cancellation
                // evidence is still unresolved. Incorporate executions first.
                foreach(string name in Get("cancel_names").Split('|').Where(n=>n.Length>0))
                    if(!new[]{"Cancelled","Filled","Rejected"}.Contains(Get("order."+RoleForName(name))))
                    { Recover("RECONCILIATION_REQUIRED"); return; }
                // Missing inventory is not cancellation proof. A fill label (or
                // cancelled order with a fill) must be reconciled to executions.
                foreach(string role in new[]{"PROTECTIVE_STOP","PROFIT_TARGET"})
                {
                    if(Get("create."+role)=="1" && !new[]{"Cancelled","Filled","Rejected"}.Contains(Get("order."+role)))
                    { Recover("RECONCILIATION_REQUIRED"); return; }
                    if(Get("order_filled."+role)=="1" && !state.Any(p=>p.Key.StartsWith("execution.",StringComparison.Ordinal) && p.Value.StartsWith(role+"|",StringComparison.Ordinal)))
                    { Recover("RECONCILIATION_REQUIRED"); return; }
                }
                snapshot=FreshSnapshot();
                if(snapshot.ActiveOrderNames.Length!=0) return;
                string positionEvidence=snapshot.PositionQuantity.ToString(CultureInfo.InvariantCulture)+"|"+snapshot.PositionSide;
                if(Get("position_rechecked")!=positionEvidence)
                { state["position_rechecked"]=positionEvidence; Save("POSITION_RECHECKED"); }
                if(snapshot.PositionQuantity==1)
                {
                    if(Get("exit_filled")=="1") { Recover("RECONCILIATION_REQUIRED"); return; }
                    if(Get("create.RECOVERY_CLOSE")=="1") return;
                    // FreshSnapshot already proves quantity, side, account and
                    // generation against the authoritative entry execution.
                    state["recovery_id"]=OrderName("RECOVERY_CLOSE");
                    try { SubmitRole("RECOVERY_CLOSE",0m); }
                    catch { Recover("RECONCILIATION_REQUIRED"); throw; }
                    return;
                }
                // The backend must attest durable financial reconciliation before
                // a flat inventory can be declared financially complete.
                if(Get("financial_complete")!="1") return;
                state["status"]="RECOVERY_COMPLETE"; Save("RECOVERY_COMPLETE");
            }
        }
        public void FinancialApplied(string admissionDigest, string executionsDigest, string checkpointDigest, string authenticator)
        {
            lock(sync)
            {
                string evidence=string.Concat(state.Where(p=>p.Key.StartsWith("execution.",StringComparison.Ordinal))
                    .OrderBy(p=>p.Key,StringComparer.Ordinal).Select(p=>p.Key+"\t"+p.Value+"\n"));
                string expected;
                using(var sha=SHA256.Create()) expected=ControlledAdmissionV3.Hex(sha.ComputeHash(Encoding.UTF8.GetBytes(evidence)));
                string payload=admissionDigest+"\n"+executionsDigest+"\n"+checkpointDigest+"\n";
                if(admissionDigest!=admission.Digest || executionsDigest!=expected ||
                    !System.Text.RegularExpressions.Regex.IsMatch(checkpointDigest,@"\A[0-9a-f]{64}\z") ||
                    !ControlledAdmissionV3.Equal(authenticator,ControlledAdmissionV3.Mac(key,
                        Encoding.UTF8.GetBytes("arms.native.financial.v3\0"+payload))))
                    throw new InvalidDataException("Unverifiable financial checkpoint receipt.");
                if(Get("financial_executions")==executionsDigest) return;
                state["financial_checkpoint"]=checkpointDigest;
                state["financial_executions"]=executionsDigest;
                state["financial_complete"]=Get("exit_filled")=="1"?"1":"0";
                Save(Get("order_id.RECOVERY_CLOSE")!=""?"RECOVERY_FINANCIAL_APPLIED":"FINANCIAL_APPLIED");
            }
        }
        public void Dispose() { writer.Dispose(); Array.Clear(key,0,key.Length); }
    }
}
