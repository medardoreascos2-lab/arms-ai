// Offline metadata doubles. No NinjaTrader binaries are loaded by this executable.
using System;
using System.IO;
using System.Collections.Generic;
using NinjaTrader.Cbi;
using NinjaTrader.Data;
using NinjaTrader.NinjaScript;
public static class ManualClock { public static DateTime UtcNow = new DateTime(2026,9,27,23,0,0,DateTimeKind.Utc); }
namespace System.Windows.Threading {
    public class DispatcherTimer {
        public TimeSpan Interval; public event EventHandler Tick;
        public void Start() {} public void Stop() {}
        public void Fire() { if(Tick!=null) Tick(this,EventArgs.Empty); }
    }
    public class Dispatcher { public void InvokeAsync(Action action) { action(); } }
}
namespace NinjaTrader.Core {
    public static class Globals { public static readonly Options GeneralOptions = new Options(); }
    public class Options { public TimeZoneInfo TimeZoneInfo = TimeZoneInfo.Utc; }
}
namespace NinjaTrader.Cbi {
    public enum Provider { Provider31, Other, Simulator }
    public enum InstrumentType { Future }
    public enum ConnectionStatus { Connected, Connecting, Disconnected, ConnectionLost }
    public class ConnectionOptions { public Provider Provider=Provider.Provider31;
        public string Name { get { throw new Exception("SECRET_ACCESS"); } } }
    public class Connection {
        public static readonly List<Connection> Connections=new List<Connection>();
        public static Connection PlaybackConnection;
        public ConnectionOptions Options=new ConnectionOptions();
        public List<InstrumentType> InstrumentTypes=new List<InstrumentType>{InstrumentType.Future};
        public ConnectionStatus PriceStatus=ConnectionStatus.Connected,Status=ConnectionStatus.Connected;
    }
    public class ConnectionStatusEventArgs {
        public Connection Connection;
        public ConnectionStatus PriceStatus=ConnectionStatus.Connected,Status=ConnectionStatus.Connected,
            PreviousPriceStatus=ConnectionStatus.Connected,PreviousStatus=ConnectionStatus.Connected;
    }
    public class MasterInstrument { public string Name="NQ";public double TickSize=.25,PointValue=20; }
    public class Instrument { public string FullName="NQ DEC26"; public DateTime Expiry=new DateTime(2026,12,1);
        public MasterInstrument MasterInstrument=new MasterInstrument(); }
}
namespace NinjaTrader.Data {
    public enum BarsPeriodType { Minute }
    public enum MarketDataType { Bid, Ask, Last }
    public class BarsPeriod { public BarsPeriodType BarsPeriodType=BarsPeriodType.Minute;public int Value=1; }
    public class TradingHours { public string Name="CME US Index Futures ETH";
        public TimeZoneInfo TimeZoneInfo=TimeZoneInfo.FindSystemTimeZoneById("Central Standard Time"); }
    public class Bars { public TradingHours TradingHours=new TradingHours(); }
    public class MarketDataEventArgs { public MarketDataType MarketDataType;public double Price;public Instrument Instrument; }
}
namespace NinjaTrader.NinjaScript {
    public enum State { SetDefaults, Historical, Realtime, Terminated }
    public enum Calculate { OnEachTick }
    public class NinjaScriptPropertyAttribute : Attribute {}
    public class Chart { public System.Windows.Threading.Dispatcher Dispatcher=new System.Windows.Threading.Dispatcher(); }
    public class Indicator {
        public State State; public string Name,Description;
        public Calculate Calculate; public bool IsOverlay,IsChartOnly,IsSuspendedWhileInactive;
        public Instrument Instrument=new Instrument(); public Bars Bars=new Bars();public BarsPeriod BarsPeriod=new BarsPeriod();
        public Chart ChartControl=new Chart();
        protected virtual void OnStateChange() {} protected virtual void OnMarketData(MarketDataEventArgs e) {}
        protected virtual void OnConnectionStatusUpdate(ConnectionStatusEventArgs e) {}
        public void Print(string value) { Console.WriteLine(value); }
    }
}
class Subject : NinjaTrader.NinjaScript.Indicators.ArmsReadOnlyL1V1 {
    public void Change(State s) { State=s;OnStateChange(); }
    public void Price(MarketDataType type,double price) { OnMarketData(new MarketDataEventArgs{MarketDataType=type,Price=price,Instrument=Instrument}); }
    public void ConnectionEvent(Connection c, ConnectionStatus price=ConnectionStatus.Connected,
        ConnectionStatus status=ConnectionStatus.Connected,
        ConnectionStatus previousPrice=ConnectionStatus.Connected,
        ConnectionStatus previousStatus=ConnectionStatus.Connected) {
        c.PriceStatus=price;c.Status=status;
        OnConnectionStatusUpdate(new ConnectionStatusEventArgs{Connection=c,PriceStatus=price,Status=status,
            PreviousPriceStatus=previousPrice,PreviousStatus=previousStatus});
    }
    public void ConnectionEventSnapshot(Connection c, ConnectionStatus price,
        ConnectionStatus status, ConnectionStatus previousPrice,
        ConnectionStatus previousStatus) {
        OnConnectionStatusUpdate(new ConnectionStatusEventArgs{Connection=c,PriceStatus=price,Status=status,
            PreviousPriceStatus=previousPrice,PreviousStatus=previousStatus});
    }
    public void Heartbeat() {
        typeof(NinjaTrader.NinjaScript.Indicators.ArmsReadOnlyL1V1).GetMethod("Heartbeat",System.Reflection.BindingFlags.NonPublic|System.Reflection.BindingFlags.Instance).Invoke(this,new object[]{null,EventArgs.Empty});
    }
}
class Program {
    static void Main(string[] args) {
        var mode=args[0];var directory=args[1];Directory.CreateDirectory(directory);
        var feed=new Connection();Connection.Connections.Add(feed);
        var s=new Subject();s.Change(State.SetDefaults);s.OutputDirectory=directory;s.ExpectedProvider="Provider31";
        if(mode=="contract")s.Instrument.FullName="NQ MAR27";
        if(mode=="provider")feed.Options.Provider=Provider.Other;
        if(mode=="expected_provider")s.ExpectedProvider="Simulator";
        if(mode=="expiry")s.Instrument.Expiry=new DateTime(2027,3,1);
        if(mode=="timezone")NinjaTrader.Core.Globals.GeneralOptions.TimeZoneInfo=TimeZoneInfo.FindSystemTimeZoneById("Eastern Standard Time");
        if(mode=="template")s.Bars.TradingHours.Name="Other";
        if(mode=="disconnected")feed.PriceStatus=ConnectionStatus.Disconnected;
        if(mode=="playback")Connection.PlaybackConnection=feed;
        if(mode=="tick")s.Instrument.MasterInstrument.TickSize=.5;
        if(mode=="point")s.Instrument.MasterInstrument.PointValue=2;
        if(mode=="historical") {s.Change(State.Historical);s.Price(MarketDataType.Bid,25000);s.Price(MarketDataType.Ask,25000.25);return;}
        s.Change(State.Realtime);
        if(mode=="connection_identity") { Connection.Connections.Clear();Connection.Connections.Add(new Connection()); }
        if(mode=="connection_event")s.ConnectionEvent(new Connection());
        if(mode=="startup_previous_disconnected")
            s.ConnectionEvent(feed,ConnectionStatus.Connected,ConnectionStatus.Connected,
                ConnectionStatus.Disconnected,ConnectionStatus.Disconnected);
        if(mode=="stale_connecting_callback")
            s.ConnectionEventSnapshot(feed,ConnectionStatus.Connecting,ConnectionStatus.Connecting,
                ConnectionStatus.Disconnected,ConnectionStatus.Disconnected);
        if(mode=="source_disconnect")
            s.ConnectionEvent(feed,ConnectionStatus.Disconnected,ConnectionStatus.Disconnected);
        if(mode=="last")s.Price(MarketDataType.Last,25000);
        else if(mode=="ask_first") {s.Price(MarketDataType.Ask,25000.25);s.Price(MarketDataType.Bid,25000);}
        else {
            double bid=mode=="zero_bid"?0:mode=="nan"?Double.NaN:mode=="infinity"?Double.PositiveInfinity:25000;
            s.Price(MarketDataType.Bid,bid);
            if(mode=="stale_side")ManualClock.UtcNow=ManualClock.UtcNow.AddSeconds(31);
            if(mode!="bid_only")s.Price(MarketDataType.Ask,mode=="zero_ask"?0:mode=="crossed"?24999:25000.25);
        }
        if(mode=="bid_update") {ManualClock.UtcNow=ManualClock.UtcNow.AddSeconds(1);s.Price(MarketDataType.Bid,24999.75);}
        if(mode=="ask_update") {ManualClock.UtcNow=ManualClock.UtcNow.AddSeconds(1);s.Price(MarketDataType.Ask,25000.50);}
        if(mode=="duplicate")s.Price(MarketDataType.Bid,25000);
        if(mode=="transient_crossed") {
            ManualClock.UtcNow=ManualClock.UtcNow.AddSeconds(1);
            s.Price(MarketDataType.Bid,25000.50);
            ManualClock.UtcNow=ManualClock.UtcNow.AddMilliseconds(1);
            s.Price(MarketDataType.Ask,25000.75);
        }
        s.Heartbeat();s.Change(State.Terminated);
        s.Price(MarketDataType.Bid,1);s.Price(MarketDataType.Ask,2); // latch stays closed
        if(mode=="restart") {
            var next=new Subject();next.Change(State.SetDefaults);next.OutputDirectory=directory;next.ExpectedProvider="Provider31";
            next.Change(State.Realtime);next.Price(MarketDataType.Bid,25000);next.Price(MarketDataType.Ask,25000.25);next.Change(State.Terminated);
        }
    }
}
