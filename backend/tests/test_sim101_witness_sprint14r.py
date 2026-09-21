"""Entire witness source with metadata-only doubles; no native accounts loaded."""
import json
import hashlib
from pathlib import Path
import re
import subprocess

import pytest

from backend.market_data.sim_binding_contract_v1 import assess_sim_binding
from backend.tests.test_sim_binding_sprint13 import fixture

SOURCE = Path('integrations/ninjatrader/ArmsSim101WitnessV1.cs')


@pytest.fixture(scope='module')
def witness(tmp_path_factory):
    folder=tmp_path_factory.mktemp('synthetic_sim101')
    source=SOURCE.read_text().replace('using System.Diagnostics;', 'using Stopwatch = Doubles.Clock;')
    source=source.replace('using System.Threading;', 'using Timer = Doubles.ManualTimer;\nusing Monitor = System.Threading.Monitor;\nusing Timeout = System.Threading.Timeout;')
    (folder/'Witness.cs').write_text(source)
    host=folder/'Host.cs'
    host.write_text(r'''
using System; using System.IO; using System.Linq; using System.Collections.Generic; using System.Threading;
using NinjaTrader.Cbi; using NinjaTrader.NinjaScript;
namespace Doubles {
 public class Clock { public static double Now; public void Start(){} public void Stop(){} public TimeSpan Elapsed {get{return TimeSpan.FromMilliseconds(Now);}} }
 public class ManualTimer:IDisposable {
  public static List<ManualTimer> All=new List<ManualTimer>(); public bool Disposed; public double Due; int period; TimerCallback cb; object state;
  public ManualTimer(TimerCallback callback,object s,int due,int p){cb=callback;state=s;Due=Clock.Now+due;period=p;All.Add(this);}
  public void Dispose(){Disposed=true;} public void Queued(){cb(state);}
  public static void Advance(double until){while(true){var t=All.Where(x=>!x.Disposed && x.Due<=until).OrderBy(x=>x.Due).FirstOrDefault();if(t==null)break;Clock.Now=t.Due;t.Due=periodNext(t);t.Queued();}Clock.Now=until;}
  static double periodNext(ManualTimer t){return t.period<0?Double.PositiveInfinity:t.Due+t.period;}
 }
}
namespace NinjaTrader.Cbi {
 public enum Provider { Simulator,Provider31,Playback,Unknown }
 public enum ConnectionStatus { Connected,Disconnected,Connecting,ConnectionLost }
 public class ConnectOptions { public Provider Provider {get{return Provider.Provider31;}} public string Name {get{throw new Exception("PRIVATE_SENTINEL");}} }
 public class Connection {
  public static List<Connection> Connections=new List<Connection>(); public ConnectOptions Options {get{return new ConnectOptions();}}
  public ConnectionStatus Status {get{return ConnectionStatus.Connected;}} public ConnectionStatus PriceStatus {get{return ConnectionStatus.Connected;}}
 }
 public class Account {
  public static List<Account> All=new List<Account>(); public static event EventHandler SimulationAccountReset;
  public static int Subscribers {get{return SimulationAccountReset==null?0:SimulationAccountReset.GetInvocationList().Length;}}
  public static void Raise(object sender){if(SimulationAccountReset!=null)SimulationAccountReset(sender,EventArgs.Empty);}
  public string TestName="Sim101"; public Provider TestProvider=Provider.Simulator; public Connection TestConnection; public bool Fault,Flip,CrossDeadline;
  int reads; public string Name {get{if(Fault)throw new Exception("PRIVATE_SENTINEL");return TestName;}}
  public Provider Provider {get{return TestProvider;}}
  public Connection Connection {get{return TestConnection;}}
  public ConnectionStatus ConnectionStatus {get{if(CrossDeadline)Doubles.Clock.Now=30000;return Flip && ++reads%2==0?ConnectionStatus.Disconnected:ConnectionStatus.Connected;}}
  public string Id {get{throw new Exception("PRIVATE_SENTINEL");}}
  public string DisplayName {get{throw new Exception("PRIVATE_SENTINEL");}}
  // No account mutators, balances, orders, positions or executions exist in this API.
 }
}
namespace NinjaTrader.NinjaScript {
 public enum State {SetDefaults,DataLoaded,Historical,Realtime,Terminated}
 public class NinjaScriptPropertyAttribute:Attribute{}
 public class Indicator {public State State;public string Name,Description;public bool IsOverlay,IsChartOnly,IsSuspendedWhileInactive;
  protected virtual void OnStateChange(){} protected void Print(string value){Console.WriteLine(value);}}
}
class Host:NinjaTrader.NinjaScript.Indicators.ArmsSim101WitnessV1 {
 public void Step(State state){State=state;OnStateChange();}
 static void Main(string[] args){
  var c=new Connection();Connection.Connections.Add(c);var a=new Account{TestConnection=c};Account.All.Add(a);
  string which=args[1];
  if(which=="real_named"||which=="external_named"||which=="prop_named")a.TestProvider=Provider.Provider31;
  if(which=="user_sim"||which=="provider_only")a.TestName="SYNTHETIC_PRIVATE_SIM";
  if(which=="none")Account.All.Clear();
  if(which=="ambiguous")Account.All.Add(new Account{TestConnection=c});
  if(which=="playback")a.TestProvider=Provider.Playback;
  if(which=="unknown_enum")a.TestProvider=(Provider)999;
  if(which=="unregistered")Connection.Connections.Clear();
  if(which=="fault")a.Fault=true;
  if(which=="unstable")a.Flip=true;
  if(which=="cross_deadline")a.CrossDeadline=true;
  var locked=new ManualResetEventSlim();var release=new ManualResetEventSlim();Thread held=null;
  if(which=="registry_busy") {held=new Thread(()=>{lock(Account.All){locked.Set();release.Wait();}});held.Start();locked.Wait();}
  var h=new Host();h.Step(State.SetDefaults);h.OutputDirectory=which=="invalid_directory"?"":args[0];h.Step(State.DataLoaded);h.Step(State.DataLoaded);
  if(held!=null){release.Set();held.Join();}
  if(which=="replacement")Account.All[0]=new Account{TestConnection=c};
  if(which=="connection_changed")a.TestConnection=new Connection();
  if(which=="renamed")a.TestName="SYNTHETIC_PRIVATE_RENAMED";
  if(which=="reset")Account.Raise(a);
  if(which=="unknown_reset")Account.Raise(null);
  if(which=="unrelated_reset")Account.Raise(new Account());
  if(which=="terminated")h.Step(State.Terminated);
  if(which=="record_limit")for(int i=0;i<9;i++)Doubles.ManualTimer.All[0].Queued();
  Doubles.ManualTimer.Advance(35000);
  foreach(var t in Doubles.ManualTimer.All)t.Queued();
  Account.Raise(a);h.Step(State.DataLoaded);h.Step(State.Terminated);
  if(Account.Subscribers!=0||Doubles.ManualTimer.All.Any(t=>!t.Disposed))throw new Exception("cleanup failed");
  foreach(var file in Directory.GetFiles(args[0],"*.jsonl"))using(var stream=new FileStream(file,FileMode.Open,FileAccess.Read,FileShare.None)){}
  Console.WriteLine("BROKER_ORDER_CALLS=0;ACCOUNT_MUTATIONS=0;CLEANUP=PASS");
 }
}
''')
    exe=folder/'Host.exe'
    compiled=subprocess.run(['C:/Windows/Microsoft.NET/Framework64/v4.0.30319/csc.exe','/nologo',
        '/out:'+str(exe),'/r:System.ComponentModel.DataAnnotations.dll','/r:System.Web.Extensions.dll',
        str(folder/'Witness.cs'),str(host)],capture_output=True,text=True)
    assert compiled.returncode==0,compiled.stdout
    return exe


@pytest.mark.parametrize('case,reason', [
    ('consistent','WINDOW_END'),('real_named','CANDIDATE_PRECONDITIONS_FAILED'),
    ('external_named','CANDIDATE_PRECONDITIONS_FAILED'),('prop_named','CANDIDATE_PRECONDITIONS_FAILED'),
    ('user_sim','NO_CANDIDATE'),('provider_only','NO_CANDIDATE'),('none','NO_CANDIDATE'),
    ('ambiguous','AMBIGUOUS_CANDIDATES'),('replacement','ACCOUNT_REPLACED'),
    ('connection_changed','CANDIDATE_PRECONDITIONS_FAILED'),('renamed','NO_CANDIDATE'),
    ('playback','CANDIDATE_PRECONDITIONS_FAILED'),('unknown_enum','CANDIDATE_PRECONDITIONS_FAILED'),
    ('unregistered','CANDIDATE_PRECONDITIONS_FAILED'),('unstable','CANDIDATE_PRECONDITIONS_FAILED'),
    ('fault','METADATA_READ_FAILED'),('registry_busy','ACCOUNT_REGISTRY_UNAVAILABLE'),
    ('reset','RESET_OBSERVED'),('unknown_reset','RESET_OBSERVED'),('unrelated_reset','WINDOW_END'),
    ('terminated','HOST_TERMINATED'),('cross_deadline','WINDOW_END'),('record_limit','RECORD_LIMIT')])
def test_bounded_metadata_witness_never_grants_proof(witness,tmp_path,case,reason):
    run=subprocess.run([str(witness),str(tmp_path),case],capture_output=True,text=True,timeout=15)
    assert run.returncode==0,run.stdout+run.stderr
    assert 'CLEANUP=PASS' in run.stdout and 'PRIVATE_SENTINEL' not in run.stdout
    files=list(tmp_path.glob('*.sim101-witness.jsonl'));assert len(files)==1
    raw=files[0].read_text();rows=[json.loads(line) for line in raw.splitlines()]
    assert raw.endswith('\n') and len(rows)<=8
    assert rows[-1]['kind']=='WITNESS_END' and rows[-1]['payload']['reason']==reason
    assert rows[-1]['payload']['reset_unsubscribed'] and rows[-1]['payload']['timers_disposed']
    assert rows[-1]['payload']['native_references_released']
    assert not any(s in raw for s in ('PRIVATE_SENTINEL','SYNTHETIC_PRIVATE','account_id','DisplayName'))
    assert all(r['builtin_sim101_proof']=='NOT_PROVEN' and r['generic_classification']=='UNKNOWN'
        and not r['future_sim_eligible'] and r['sim_execution_authority']=='DISABLED' for r in rows)
    assert [r['sequence'] for r in rows]==list(range(len(rows)))
    if case=='record_limit': assert len(rows)==8
    assert all(r['elapsed_ms']<30000 for r in rows[:-1])
    if case in ('consistent','unrelated_reset'):
        assert len(rows)==7 and rows[0]['kind']=='WITNESS_START'
        assert rows[-1]['elapsed_ms']==30000
        assert all(r['payload']['candidate_status']=='CANDIDATE_CONSISTENT_NOT_PROVEN' for r in rows[:-1])


def test_invalid_destination_does_not_start_discovery(witness,tmp_path):
    run=subprocess.run([str(witness),str(tmp_path),'invalid_directory'],capture_output=True,text=True,timeout=15)
    assert run.returncode==0 and not list(tmp_path.glob('*.jsonl'))


@pytest.mark.parametrize('case',['real_renamed','external_named','prop_named','user_sim','provider_only',
    'name_only','connection_mismatch','replacement','binding_mismatch','stale','ambiguous','consistent_candidate'])
def test_no_candidate_claim_can_enter_generic_or_future_sim_authority(case):
    binding,now,snapshot=fixture()
    snapshot.update(proof_contract='BUILTIN_SIM101',classification='PROVEN_BUILTIN_SIM101',
        candidate_status='CANDIDATE_CONSISTENT_NOT_PROVEN',name='Sim101',provider='Simulator')
    if case=='connection_mismatch':snapshot['connection_ref']='synthetic-other'
    if case in ('replacement','binding_mismatch'):snapshot['account_ref']='synthetic-other'
    if case=='stale':snapshot['observed_at']='2000-01-01T00:00:00+00:00'
    if case=='ambiguous':snapshot['account_count']=2
    for synthetic in (False,True):
        result=assess_sim_binding(snapshot,binding,now,synthetic=synthetic)
        assert result['sim_classification_status']=='UNKNOWN'
        assert not result['future_sim_eligible'] and result['sim_execution_authority']=='DISABLED'


def test_native_source_has_no_mutation_financial_or_identifier_surface():
    source=SOURCE.read_text()
    forbidden=r'\b(?:Submit|Cancel|CancelAllOrders|Change|Flatten|CreateOrder|ResetSimulationAccount|Positions|Orders|Executions|DisplayName|Id|GetAccountItem)\s*[.(]'
    assert not re.search(forbidden,source)
    assert not re.search(r'public\s+(?:Account|Connection)\b',source)
    assert 'PROVEN_BUILTIN_SIM101' not in source
    assert 'Account.SimulationAccountReset += OnReset' in source
    assert 'Account.SimulationAccountReset -= OnReset' in source


def test_reviewed_authority_artifact_cannot_claim_builtin_proof():
    audit=json.loads(Path('backend/tests/builtin_sim101_authority_sprint14r.json').read_text())
    assert audit['generic_classifications']==['PROVEN_SIMULATION','PROVEN_NON_SIMULATION','UNKNOWN']
    assert audit['builtin_sim101_proof']=='NOT_PROVEN'
    assert audit['accepted_builtin_proof_mechanisms']==[]
    assert not audit['future_sim_eligible'] and audit['sim_execution_authority']=='DISABLED'
    assert not audit['live_authority']
    witness=audit['witness']
    assert witness['native_execution_performed'] and witness['actual_account_access_performed']
    native=audit['native_adjudication']
    assert native['native_witness_consistency']=='PASS' and native['builtin_sim101_identity']=='NOT_PROVEN'
    assert native['generic_sim_classification']=='UNKNOWN' and not native['adjudicator_account_api_access']
    assert not any(witness['boundary_mutators_reachable'].values())
    assert witness['window_ms']==30000 and witness['maximum_records']==8
    assert witness['matching_result']=='CANDIDATE_CONSISTENT_NOT_PROVEN'
    assert witness['source']==SOURCE.as_posix()


def test_native_capture_matches_reviewed_hash_and_scalar_projection():
    audit=json.loads(Path('backend/tests/builtin_sim101_authority_sprint14r.json').read_text())
    native=audit['native_adjudication']
    evidence=Path('.arms-dev/ninjatrader-current')/native['artifact']
    if not evidence.exists():
        pytest.skip('Private native evidence unavailable; do not substitute synthetic evidence')
    raw=evidence.read_bytes()
    # Validate the approved bytes before any assertion could render private values.
    assert hashlib.sha256(raw).hexdigest()==native['artifact_sha256']
    assert len(raw)==native['artifact_bytes'] and raw.endswith(b'\n')
    rows=[json.loads(line) for line in raw.decode('utf-8').splitlines()]
    assert len(rows)==native['record_count']==7
    assert [r['sequence'] for r in rows]==list(range(7))
    assert [r['kind'] for r in rows]==['WITNESS_START']+['WITNESS_SAMPLE']*5+['WITNESS_END']
    assert [r['elapsed_ms'] for r in rows]==native['elapsed_ms']
    assert all(r['elapsed_ms']<30000 for r in rows[:-1])
    assert rows[-1]['elapsed_ms']>=30000
    assert rows[0]['event_time']==native['capture_start'] and rows[-1]['event_time']==native['capture_end']
    assert [r['event_time'] for r in rows]==sorted(r['event_time'] for r in rows)
    assert len(set(raw.splitlines()))==7
    keys={'schema','session','sequence','event_time','elapsed_ms','kind','observation_only',
        'builtin_sim101_proof','generic_classification','future_sim_eligible','sim_execution_authority','payload'}
    for row in rows:
        assert set(row)==keys
        assert row['schema']==native['schema'] and row['session']==native['observation_session']
        assert row['observation_only'] is True
        assert row['builtin_sim101_proof']=='NOT_PROVEN' and row['generic_classification']=='UNKNOWN'
        assert row['future_sim_eligible'] is False and row['sim_execution_authority']=='DISABLED'
    assert all(row['payload']==native['sample_payload'] for row in rows[:-1])
    assert rows[-1]['payload']==dict(reason='WINDOW_END',reset_unsubscribed=True,
        timers_disposed=True,native_references_released=True,window_ms=30000,maximum_records=8)


@pytest.mark.parametrize('claim',['UNKNOWN','PROVEN_SIMULATION','PROVEN_BUILTIN_SIM101'])
def test_consistent_native_sample_cannot_establish_account_eligibility(claim):
    audit=json.loads(Path('backend/tests/builtin_sim101_authority_sprint14r.json').read_text())
    binding,now,snapshot=fixture()
    snapshot.update(audit['native_adjudication']['sample_payload'])
    snapshot.update(classification=claim,operator_approved=True)
    result=assess_sim_binding(snapshot,binding,now)
    assert result['sim_classification_status']=='UNKNOWN'
    assert result['future_sim_eligible'] is False
    assert result['external_order_authority'] is False
    assert result['sim_execution_authority']=='DISABLED'


def test_installed_sdk_compilation_and_cbi_call_allowlist(tmp_path):
    """Compile and inspect IL metadata only; never instantiate the SDK or witness."""
    framework=Path('C:/Windows/Microsoft.NET/Framework64/v4.0.30319')
    native=Path('C:/Program Files/NinjaTrader 8/bin')
    assert hashlib.sha256((native/'NinjaTrader.Core.dll').read_bytes()).hexdigest()==\
        '89d30ce74dfb21c26c0819db1f5979799b152d522bbfbc436a3b2cfb495b9408'
    shim=tmp_path/'IndicatorShim.cs'
    shim.write_text('namespace NinjaTrader.NinjaScript.Indicators { public class Indicator : NinjaTrader.NinjaScript.IndicatorBase {} }')
    dll=tmp_path/'Witness.dll'
    references=['System.ComponentModel.DataAnnotations.dll','System.Web.Extensions.dll','System.Xaml.dll',
        str(framework/'WPF/WindowsBase.dll'),str(framework/'WPF/PresentationCore.dll'),
        str(framework/'WPF/PresentationFramework.dll'),str(native/'NinjaTrader.Core.dll'),str(native/'NinjaTrader.Gui.dll')]
    result=subprocess.run([str(framework/'csc.exe'),'/nologo','/target:library','/out:'+str(dll),
        *['/r:'+r for r in references],str(shim),str(SOURCE.resolve())],capture_output=True,text=True)
    assert result.returncode==0,result.stdout
    inspect=tmp_path/'Inspect.ps1'
    inspect.write_text(r'''
param([string]$Target)
$ErrorActionPreference='Stop'
[AppDomain]::CurrentDomain.add_ReflectionOnlyAssemblyResolve({param($sender,$e)
 $file=Join-Path 'C:\Program Files\NinjaTrader 8\bin' ((New-Object Reflection.AssemblyName($e.Name)).Name+'.dll')
 if(Test-Path -LiteralPath $file){return [Reflection.Assembly]::ReflectionOnlyLoadFrom($file)}
 return [Reflection.Assembly]::ReflectionOnlyLoad($e.Name)
})
$opcodes=@{}
foreach($field in [Reflection.Emit.OpCodes].GetFields([Reflection.BindingFlags]'Public,Static')){
 $op=$field.GetValue($null);$opcodes[([int]$op.Value -band 65535)]=$op
}
$asm=[Reflection.Assembly]::ReflectionOnlyLoadFrom($Target)
$calls=New-Object 'System.Collections.Generic.HashSet[string]'
foreach($type in $asm.GetTypes()){
 $flags=[Reflection.BindingFlags]'Public,NonPublic,Instance,Static,DeclaredOnly'
 foreach($method in @($type.GetMethods($flags)) + @($type.GetConstructors($flags))){
  $body=$method.GetMethodBody();if($null -eq $body){continue};$bytes=$body.GetILAsByteArray();$i=0
  while($i -lt $bytes.Length){
   $code=[int]$bytes[$i];$i++
   if($code -eq 254){$code=65024+[int]$bytes[$i];$i++}
   $op=$opcodes[$code];if($null -eq $op){throw ('Unknown opcode '+$code+' at '+$i+' in '+$method.Name)}
   if($op.OperandType -eq [Reflection.Emit.OperandType]::InlineMethod){
    $token=[BitConverter]::ToInt32($bytes,$i)
    $genericMethods=if($method -is [Reflection.MethodInfo]){$method.GetGenericArguments()}else{@()}
    $callee=$method.Module.ResolveMethod($token,$type.GetGenericArguments(),[Type[]]$genericMethods)
    if($null -eq $callee){throw 'Unresolved method'}
    if($callee.DeclaringType.Namespace -eq 'NinjaTrader.Cbi'){[void]$calls.Add($callee.DeclaringType.FullName+'::'+$callee.Name)}
   }
   switch($op.OperandType.ToString()){
    'InlineNone'{}
    'ShortInlineBrTarget'{$i++} 'ShortInlineI'{$i++} 'ShortInlineVar'{$i++}
    'InlineVar'{$i+=2}
    'InlineI8'{$i+=8} 'InlineR'{$i+=8}
    'InlineSwitch'{$count=[BitConverter]::ToInt32($bytes,$i);$i+=4+4*$count}
    default{$i+=4}
   }
  }
 }
}
@($calls | Sort-Object) | ConvertTo-Json -Compress
''')
    result=subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(inspect),str(dll)],capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    calls=set(json.loads(result.stdout))
    expected={
        'NinjaTrader.Cbi.Account::get_All','NinjaTrader.Cbi.Account::get_Name',
        'NinjaTrader.Cbi.Account::get_Provider','NinjaTrader.Cbi.Account::get_Connection',
        'NinjaTrader.Cbi.Account::get_ConnectionStatus',
        'NinjaTrader.Cbi.Account::add_SimulationAccountReset','NinjaTrader.Cbi.Account::remove_SimulationAccountReset',
        'NinjaTrader.Cbi.Connection::get_Connections','NinjaTrader.Cbi.Connection::get_Options',
        'NinjaTrader.Cbi.Connection::get_Status','NinjaTrader.Cbi.Connection::get_PriceStatus',
        'NinjaTrader.Cbi.ConnectOptions::get_Provider',
    }
    assert calls==expected
