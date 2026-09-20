// One-shot calendar metadata capture. No accounts, market admission or orders.
// Does not change ArmsReadOnlyMarketV1. Output stays in a private local directory.
using System;
using System.ComponentModel.DataAnnotations;
using System.IO;
using System.Linq;
using System.Text;
using System.Web.Script.Serialization;
using NinjaTrader.Data;
using NinjaTrader.NinjaScript;

namespace NinjaTrader.NinjaScript.Indicators
{
    public class ArmsCalendarEvidenceV1 : Indicator
    {
        private bool attempted;
        [NinjaScriptProperty]
        [Display(Name = "Private evidence directory", Order = 1, GroupName = "ARMS calendar")]
        public string OutputDirectory { get; set; }

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Name = "ArmsCalendarEvidenceV1";
                Description = "One-shot loaded calendar metadata; no execution authority.";
                IsOverlay = true;
                IsChartOnly = true;
                OutputDirectory = "";
            }
            else if (State == State.DataLoaded && !attempted)
            {
                attempted = true;
                try
                {
                    if (String.IsNullOrWhiteSpace(OutputDirectory) || !Path.IsPathRooted(OutputDirectory)
                        || Path.GetPathRoot(OutputDirectory).StartsWith(@"\\") || !Directory.Exists(OutputDirectory)
                        || Core.Globals.GeneralOptions.TimeZoneInfo.Id != "UTC"
                        || Instrument.FullName != "NQ DEC26" || Instrument.MasterInstrument.Name != "NQ"
                        || Instrument.MasterInstrument.TickSize != .25 || Instrument.MasterInstrument.PointValue != 20
                        || BarsPeriod.BarsPeriodType != BarsPeriodType.Minute || BarsPeriod.Value != 1
                        || Bars.TradingHours.Name != "CME US Index Futures ETH")
                        throw new InvalidOperationException();
                    var hours = Bars.TradingHours;
                    var queries = new[] {
                        "2026-09-21T20:45:00", "2026-09-21T21:00:00", "2026-09-21T22:00:00",
                        "2026-09-25T21:00:00", "2026-09-27T22:00:00",
                        "2026-10-30T21:00:00", "2026-11-02T22:00:00",
                        "2026-11-25T23:00:00", "2026-11-26T18:00:00", "2026-11-26T23:00:00",
                        "2026-11-27T18:15:00", "2026-12-24T18:15:00", "2026-12-25T12:00:00" };
                    var samples = queries.Select(q => {
                        var iterator = new SessionIterator(Bars);
                        var at = DateTime.ParseExact(q, "yyyy-MM-ddTHH:mm:ss", System.Globalization.CultureInfo.InvariantCulture);
                        iterator.GetNextSession(at, true);
                        // Keep native wall values and Kind verbatim. Do not relabel
                        // local/Unspecified values UTC before independent comparison.
                        return new { query_configured_time = q, includes_end = true,
                            begin = iterator.ActualSessionBegin.ToString("o"), begin_kind = iterator.ActualSessionBegin.Kind.ToString(),
                            end = iterator.ActualSessionEnd.ToString("o"), end_kind = iterator.ActualSessionEnd.Kind.ToString(),
                            trading_day = iterator.ActualTradingDayExchange.ToString("yyyy-MM-dd") };
                    }).ToArray();
                    var session = Guid.NewGuid().ToString();
                    var evidence = new { schema = "arms.nt.calendar-evidence.v1", session = session,
                        event_time = DateTime.UtcNow.ToString("o"), observation_only = true,
                        contract = Instrument.FullName, expiry_month = Instrument.Expiry.ToString("yyyy-MM-dd"),
                        instrument = Instrument.MasterInstrument.Name, tick_size = Instrument.MasterInstrument.TickSize,
                        point_value = Instrument.MasterInstrument.PointValue, bars_type = "Minute", bars_value = 1,
                        application_timezone = Core.Globals.GeneralOptions.TimeZoneInfo.Id,
                        system_timezone = TimeZoneInfo.Local.Id,
                        template = hours.Name, template_version = hours.Version, template_timezone = hours.TimeZoneInfo.Id,
                        sessions = hours.Sessions.Select(s => new { begin_day = s.BeginDay.ToString(), begin_time = s.BeginTime,
                            end_day = s.EndDay.ToString(), end_time = s.EndTime, trading_day = s.TradingDay.ToString() }).ToArray(),
                        holiday_dates = hours.Holidays.Keys.OrderBy(d => d).Select(d => d.ToString("yyyy-MM-dd")).ToArray(),
                        partial_holiday_dates = hours.PartialHolidays.Keys.OrderBy(d => d).Select(d => d.ToString("yyyy-MM-dd")).ToArray(),
                        partial_holidays_2026 = hours.PartialHolidays.OrderBy(p => p.Key).Where(p => p.Key.Year == 2026).Select(p => new {
                            date = p.Key.ToString("yyyy-MM-dd"), early_end = p.Value.IsEarlyEnd, late_begin = p.Value.IsLateBegin,
                            constraint = SessionMetadata(p.Value.Constraint),
                            sessions = p.Value.Sessions.Select(s => SessionMetadata(s)).ToArray() }).ToArray(),
                        samples = samples, completion = "COMPLETE_METADATA_ONLY", native_certification = "PENDING_REVIEW" };
                    using (var stream = new FileStream(Path.Combine(OutputDirectory, session + ".calendar.jsonl"),
                        FileMode.CreateNew, FileAccess.Write, FileShare.Read))
                    using (var output = new StreamWriter(stream, new UTF8Encoding(false)))
                        output.WriteLine(new JavaScriptSerializer().Serialize(evidence));
                    Print("ARMS_CALENDAR_EVIDENCE_COMPLETE");
                }
                catch { Print("ARMS_CALENDAR_EVIDENCE_FAILED"); }
            }
        }

        private static object SessionMetadata(Session s)
        {
            return new { begin_day = s.BeginDay.ToString(), begin_time = s.BeginTime,
                end_day = s.EndDay.ToString(), end_time = s.EndTime, trading_day = s.TradingDay.ToString() };
        }
    }
}
