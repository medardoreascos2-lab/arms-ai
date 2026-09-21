// Offline metadata and Windows timezone probe. NEVER executes NinjaTrader code.
// Candidate queries are not native results or certification evidence.
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Security.Cryptography;
using System.Web.Script.Serialization;

public static class SessionIteratorContractProbe
{
    private static string sdk;
    private static string Hex(byte[] data) { return BitConverter.ToString(data).Replace("-", "").ToLowerInvariant(); }
    private static string Hash(byte[] data) { using (var h = SHA256.Create()) return Hex(h.ComputeHash(data)); }
    private static string Stamp(DateTime t) { return t.ToString("o", CultureInfo.InvariantCulture); }
    private static Assembly Resolve(object sender, ResolveEventArgs args)
    {
        var name = new AssemblyName(args.Name);
        var path = Path.Combine(sdk, name.Name + ".dll");
        return File.Exists(path) ? Assembly.ReflectionOnlyLoadFrom(path) : Assembly.ReflectionOnlyLoad(args.Name);
    }
    private static object Method(MethodBase m)
    {
        var body = m.GetMethodBody();
        var il = body == null ? null : body.GetILAsByteArray();
        return new { name = m.Name, signature = m.ToString(), implementation_flags = m.GetMethodImplementationFlags().ToString(),
            il_bytes = il == null ? 0 : il.Length, il_sha256 = il == null ? null : Hash(il),
            il_hex = il == null || il.Length > 256 ? null : Hex(il),
            parameters = m.GetParameters().Select(p => new { name = p.Name, type = p.ParameterType.FullName }).ToArray() };
    }
    private static object Metadata(Assembly assembly, string name)
    {
        var t = assembly.GetType(name, true);
        var flags = BindingFlags.Public | BindingFlags.Instance | BindingFlags.Static | BindingFlags.DeclaredOnly;
        var names = new[] { "GetNextSession", "get_ActualSessionBegin", "get_ActualSessionEnd", "get_ActualTradingDayExchange",
            "CalculateTradingDay", "IsNewSession", "IsInSession", "get_TimeZoneInfo", "get_Sessions", "Get" };
        return new { type = name, constructors = t.GetConstructors(flags).Select(Method).ToArray(),
            methods = t.GetMethods(flags).Where(m => names.Contains(m.Name)).Select(m => Method(m)).ToArray(),
            fields = t.GetFields(BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance | BindingFlags.DeclaredOnly)
                .Select(f => new { name = f.Name, type = f.FieldType.FullName }).ToArray() };
    }
    private static object Representation(string domain, DateTime value, DateTime? instant, bool meaningful)
    {
        return new { domain = domain, text = Stamp(value), kind = value.Kind.ToString(), ticks = value.Ticks,
            equivalent_utc = instant.HasValue ? Stamp(instant.Value) : null, meaningful_for_domain = meaningful,
            native_acceptance = "NOT_OBSERVED" };
    }
    private static object Matrix(DateTime utc, long offset)
    {
        var chicago = TimeZoneInfo.FindSystemTimeZoneById("Central Standard Time");
        var wall = TimeZoneInfo.ConvertTimeFromUtc(utc, chicago);
        var local = TimeZoneInfo.ConvertTimeFromUtc(utc, TimeZoneInfo.Local);
        // Specifying a Kind below is an explicit diagnostic representation, never an exporter repair.
        return new { offset_ticks = offset, utc = Stamp(utc),
            representations = new[] {
                Representation("UTC", utc, utc, true),
                Representation("APPLICATION_UTC_WALL", DateTime.SpecifyKind(utc, DateTimeKind.Unspecified), utc, true),
                Representation("TRADING_HOURS_WALL", wall, utc, true),
                Representation("OS_LOCAL", local, utc, true),
                Representation("CHICAGO_WALL_MISLABELED_UTC", DateTime.SpecifyKind(wall, DateTimeKind.Utc), null, false),
                Representation("UTC_WALL_MISLABELED_OS_LOCAL", DateTime.SpecifyKind(utc, DateTimeKind.Local), null,
                    TimeZoneInfo.Local.GetUtcOffset(utc) == TimeSpan.Zero) } };
    }
    public static int Main(string[] args)
    {
        if (args.Length != 1) return 2;
        sdk = Path.GetFullPath(args[0]);
        AppDomain.CurrentDomain.ReflectionOnlyAssemblyResolve += Resolve;
        var path = Path.Combine(sdk, "NinjaTrader.Core.dll");
        var assembly = Assembly.ReflectionOnlyLoadFrom(path);
        var iterator = assembly.GetType("NinjaTrader.Data.SessionIterator", true);
        var advance = iterator.GetMethod("GetNextSession", new[] { typeof(DateTime), typeof(bool) });
        var il = advance.GetMethodBody().GetILAsByteArray();
        var constantFalse = Hex(il) == "20000000002a" || Hex(il) == "162a";
        var end = new DateTime(2026, 9, 14, 21, 0, 0, DateTimeKind.Utc);
        long[] offsets = { 0, 1, TimeSpan.TicksPerMillisecond, TimeSpan.TicksPerSecond };
        var scenarios = new List<object>();
        Action<string, DateTime[], bool> add = (name, queries, include) => scenarios.Add(new {
            name = name, query_sequence = queries.Select(Stamp).ToArray(), include_end_time = include,
            boolean_results = (object)null, returned_bounds = (object)null, status = "NOT_EXECUTED_NATIVE_HOST_UNAVAILABLE" });
        var first = new DateTime(2026, 9, 14, 0, 0, 0, DateTimeKind.Utc);
        foreach (var offset in offsets)
            add("REUSED_ITERATOR_END_PLUS_" + offset + "_TICKS", new[] { first, end.AddTicks(offset) }, true);
        add("REPEATED_IDENTICAL_QUERY", new[] { first, first }, true);
        add("INDEPENDENT_NEXT_SESSION_QUERY", new[] { end.AddHours(1).AddSeconds(1) }, true);
        add("MAINTENANCE_BREAK", new[] { first, end.AddMinutes(30) }, true);
        add("SUNDAY_MONDAY", new[] { first.AddHours(-2), first, end }, true);
        add("CONSECUTIVE_SESSIONS", new[] { first, first.AddDays(1), first.AddDays(2), first.AddDays(3) }, true);
        add("WEEKEND_REOPEN", new[] { end.AddDays(4), end.AddDays(6).AddHours(1).AddSeconds(1) }, true);
        add("END_EXCLUSIVE_HYPOTHESIS", new[] { first, end }, false);
        var result = new { schema = "arms.sprint16ar3.offline-contract-probe.v1", classification = "OFFLINE_METADATA_AND_TIMEZONE_ONLY",
            runtime_admission = false, certification_evidence = false, native_method_invoked = false,
            reflection_only = assembly.ReflectionOnly, sdk_version = assembly.GetName().Version.ToString(),
            core_sha256 = Hash(File.ReadAllBytes(path)), module_mvid = assembly.ManifestModule.ModuleVersionId.ToString(),
            exposed_getnextsession_constant_false = constantFalse,
            execution_gate = constantFalse ? "EXPOSED_BODY_CONTRADICTS_OBSERVED_NATIVE_SUCCESS" : "NATIVE_HOST_NOT_ESTABLISHED",
            native_offline_harness_status = "BLOCKED_NO_VALIDATED_NATIVE_EXECUTION_HOST",
            dotnet_datetime_resolution_ticks = 1, ninjatrader_query_precision_ticks = (object)null,
            os_timezone = TimeZoneInfo.Local.Id,
            metadata = new[] { Metadata(assembly, "NinjaTrader.Data.SessionIterator"), Metadata(assembly, "NinjaTrader.Data.TradingHours") },
            boundary_matrix = offsets.Select(x => Matrix(end.AddTicks(x), x)).ToArray(),
            native_boundary_scenarios = scenarios,
            loaded_for_execution = AppDomain.CurrentDomain.GetAssemblies().Where(a => a.GetName().Name.StartsWith("NinjaTrader")).Select(a => a.GetName().Name).ToArray() };
        Console.WriteLine(new JavaScriptSerializer { MaxJsonLength = 1024 * 1024 }.Serialize(result));
        return 0;
    }
}
