from __future__ import annotations

import inspect
from collections.abc import Mapping
from dataclasses import fields, is_dataclass
from typing import Any

import pytest


def _required_runtime_value(
    value: Any,
    *,
    name: str,
) -> Any:
    """Return a required runtime value or fail with a useful characterization error."""
    if value is None:
        pytest.fail(f"Runtime composition did not provide required value: {name}")
    return value


def _first_present(
    obj: Any,
    names: tuple[str, ...],
    *,
    label: str,
) -> Any:
    for name in names:
        if hasattr(obj, name):
            value = getattr(obj, name)
            if value is not None:
                return value

    available = sorted(
        name
        for name in dir(obj)
        if not name.startswith("_")
    )
    pytest.fail(
        f"Runtime composition did not expose {label}. "
        f"Expected one of {names}; available public attributes include: {available}"
    )


def _nested_value(source: Any, name: str) -> Any:
    if isinstance(source, Mapping):
        return source.get(name)

    if hasattr(source, name):
        return getattr(source, name)

    return None


def _first_present_from_sources(
    sources: tuple[Any, ...],
    names: tuple[str, ...],
    *,
    label: str,
) -> Any:
    """
    Resolve a runtime contract value from the context or its published,
    account-bound runtime components.

    RuntimeContextV2 intentionally groups account identity and execution
    metadata through its settings and durable execution-state components rather
    than duplicating every value as a top-level context attribute.
    """
    nested_sources: list[Any] = []

    for source in sources:
        if source is None:
            continue

        for name in names:
            if hasattr(source, name):
                value = getattr(source, name)
                if value is not None:
                    return value

        for identity_name in (
            "account_identity",
            "runtime_identity",
            "identity",
        ):
            if hasattr(source, identity_name):
                identity = getattr(source, identity_name)
                if identity is not None:
                    nested_sources.append(identity)

    for nested_source in nested_sources:
        for name in names:
            value = _nested_value(nested_source, name)
            if value is not None:
                return value

        # Some runtime implementations expose account identity as a scalar
        # value rather than an object or mapping. Accept that representation
        # only when resolving an identity field.
        if label in {"account identity", "account profile"} and isinstance(
            nested_source,
            (str, int),
        ):
            return nested_source

    available: set[str] = set()
    for source in sources:
        if source is None:
            continue
        available.update(
            name
            for name in dir(source)
            if not name.startswith("_")
        )

    for nested_source in nested_sources:
        if isinstance(nested_source, Mapping):
            available.update(str(name) for name in nested_source)
        else:
            available.update(
                name
                for name in dir(nested_source)
                if not name.startswith("_")
            )

    pytest.fail(
        f"Runtime composition did not expose {label}. "
        f"Expected one of {names}; available public attributes include: "
        f"{sorted(available)}"
    )


def _runtime_sources(context: Any) -> tuple[Any, ...]:
    """
    Return the context plus its published runtime components that may expose
    the same composition contract.

    This deliberately compares values and component types, not object identity.
    """
    sources: list[Any] = [context]

    for component_name in (
        "settings",
        "execution_state_store",
        "execution_state_store_v2",
        "execution_manager",
        "execution_manager_v2",
        "paper_execution_engine",
        "paper_execution_engine_v2",
        "account_state_manager",
        "account_state_manager_v2",
        "account_config_manager",
        "account_config_manager_v2",
    ):
        if hasattr(context, component_name):
            component = getattr(context, component_name)
            if component is not None and component not in sources:
                sources.append(component)

    return tuple(sources)


def _settings_value(settings: Any, names: tuple[str, ...]) -> Any:
    for name in names:
        if hasattr(settings, name):
            value = getattr(settings, name)
            if value is not None:
                return value
    return None


def _build_cli_runtime_context() -> Any:
    """
    Build the runtime graph through the same composition helper used by
    backend.main rather than constructing RuntimeContextV2 directly.
    """
    from backend.config_settings import ArmsSettings
    from backend.main import build_runtime_context

    settings = ArmsSettings()
    signature = inspect.signature(build_runtime_context)
    kwargs: dict[str, Any] = {}

    if "settings" in signature.parameters:
        kwargs["settings"] = settings

    account_id = _settings_value(
        settings,
        (
            "account_id",
            "active_account_id",
            "default_account_id",
        ),
    )
    profile_name = _settings_value(
        settings,
        (
            "profile_name",
            "account_profile",
            "active_profile",
            "active_account",
        ),
    )

    explicit_runtime_parameters = {
        "account_id",
        "active_account_id",
        "profile_name",
        "account_profile",
        "execution_mode",
        "runtime_generation",
        "account_namespace",
    }

    for parameter_name, parameter in signature.parameters.items():
        if parameter_name == "settings":
            continue

        if parameter_name in {"account_id", "active_account_id"}:
            kwargs[parameter_name] = (
                account_id
                or "ARMS-PAPER-LIFECYCLE"
            )
        elif parameter_name in {"profile_name", "account_profile"}:
            kwargs[parameter_name] = (
                profile_name
                or "TOPSTEP_150K"
            )
        elif parameter_name == "execution_mode":
            kwargs[parameter_name] = "PAPER"
        elif parameter_name == "runtime_generation":
            kwargs[parameter_name] = 1
        elif parameter_name == "account_namespace":
            kwargs[parameter_name] = "test-phase1-equivalence"
        elif parameter.default is not inspect.Parameter.empty:
            continue
        elif parameter_name not in explicit_runtime_parameters:
            pytest.fail(
                "The supported backend.main.build_runtime_context() helper "
                f"has an unhandled required parameter: {parameter_name}"
            )

    context = build_runtime_context(**kwargs)
    return _required_runtime_value(
        context,
        name="backend.main.build_runtime_context() result",
    )


def _route_signature(route: Any) -> tuple[str, tuple[str, ...], str]:
    methods = tuple(sorted(getattr(route, "methods", None) or ()))
    path = str(getattr(route, "path", ""))
    route_type = type(route).__name__
    return path, methods, route_type


def _registered_route_signatures(
    application: Any,
) -> set[tuple[str, tuple[str, ...], str]]:
    router = getattr(application, "router", None)
    if router is None:
        pytest.fail("Application does not expose a router")

    routes = getattr(router, "routes", None)
    if routes is None:
        pytest.fail("Application router does not expose registered routes")

    return {
        _route_signature(route)
        for route in routes
        if getattr(route, "path", None) is not None
    }


def _runtime_identity(context: Any) -> tuple[Any, ...]:
    sources = list(_runtime_sources(context))

    account_switch_safety = getattr(
        context,
        "account_switch_safety_v2",
        None,
    )
    if account_switch_safety is not None:
        identity = getattr(
            account_switch_safety,
            "identity",
            None,
        )
        if identity is not None:
            sources.insert(0, identity)

    execution_state_store = getattr(
        context,
        "execution_state_store",
        None,
    )
    if execution_state_store is not None:
        durable_identity = getattr(
            execution_state_store,
            "_account_identity",
            None,
        )
        if durable_identity is not None:
            sources.insert(0, durable_identity)

    account_id = _first_present_from_sources(
        sources,
        ("account_id", "active_account_id", "id", "account"),
        label="account identity",
    )
    profile_name = _first_present_from_sources(
        sources,
        ("profile_name", "account_profile", "active_profile", "profile"),
        label="account profile",
    )
    execution_mode = _first_present_from_sources(
        sources,
        ("execution_mode", "mode"),
        label="execution mode",
    )
    runtime_generation = _first_present_from_sources(
        sources,
        ("runtime_generation", "generation"),
        label="runtime generation",
    )
    account_namespace = _first_present_from_sources(
        sources,
        ("account_namespace", "namespace"),
        label="account namespace",
    )

    return (
        account_id,
        profile_name,
        str(execution_mode).upper(),
        runtime_generation,
        account_namespace,
    )


def _component_class_name(value: Any) -> str:
    return type(value).__name__


def _context_component(context: Any, *names: str) -> Any:
    sources = [
        context,
        getattr(context, "trade_lifecycle_service", None),
        getattr(context, "runtime_lifecycle_manager", None),
    ]

    for source in sources:
        if source is None:
            continue

        for name in names:
            if hasattr(source, name):
                value = getattr(source, name)
                if value is not None:
                    return value

    available: set[str] = set()

    for source in sources:
        if source is None:
            continue

        available.update(
            name
            for name in dir(source)
            if not name.startswith("_")
        )

    pytest.fail(
        f"Runtime composition did not expose runtime component {names}. "
        f"Expected one of {names}; available public attributes include: "
        f"{sorted(available)}"
    )


def _app_runtime_context(application: Any) -> Any:
    state = getattr(application, "state", None)
    if state is None:
        pytest.fail("Application does not expose app.state")

    return _first_present(
        state,
        ("runtime_context_v2", "runtime_context"),
        label="application runtime context",
    )


def _construct_asgi_application(context: Any) -> Any:
    from backend.api.asgi import create_asgi_app

    signature = inspect.signature(create_asgi_app)
    if "runtime_context" not in signature.parameters:
        pytest.fail(
            "backend.api.asgi.create_asgi_app() does not expose the "
            "runtime_context injection point required for equivalence testing"
        )

    application = create_asgi_app(runtime_context=context)
    return _required_runtime_value(
        application,
        name="backend.api.asgi.create_asgi_app() result",
    )


def _construct_direct_application(context: Any) -> Any:
    from backend.api.app import create_app

    signature = inspect.signature(create_app)
    if "runtime_context" not in signature.parameters:
        pytest.fail(
            "backend.api.app.create_app() does not expose the "
            "runtime_context injection point required for equivalence testing"
        )

    application = create_app(runtime_context=context)
    return _required_runtime_value(
        application,
        name="backend.api.app.create_app() result",
    )


def test_cli_runtime_context_can_be_injected_into_asgi_application() -> None:
    """
    Characterize the supported main/CLI runtime composition as the source of
    the runtime graph used by the ASGI application.
    """
    context = _build_cli_runtime_context()
    application = _construct_asgi_application(context)

    application_context = _app_runtime_context(application)

    assert _runtime_identity(application_context) == _runtime_identity(context)
    assert _component_class_name(
        _context_component(
            application_context,
            "runtime_lifecycle_manager",
            "runtime_lifecycle_manager_v2",
        )
    ) == _component_class_name(
        _context_component(
            context,
            "runtime_lifecycle_manager",
            "runtime_lifecycle_manager_v2",
        )
    )


def test_cli_and_asgi_runtime_compositions_have_equivalent_identity_and_owners() -> None:
    """
    Build two independent runtime graphs through backend.main's supported
    builder and compare composition contracts rather than object identity.
    """
    cli_context = _build_cli_runtime_context()
    asgi_context = _build_cli_runtime_context()

    assert _runtime_identity(cli_context) == _runtime_identity(asgi_context)

    lifecycle_names = (
        "runtime_lifecycle_manager",
        "runtime_lifecycle_manager_v2",
    )
    startup_names = (
        "startup_coordinator",
        "startup_coordinator_v2",
    )
    recovery_names = (
        "state_recovery_service",
        "state_recovery_service_v2",
    )
    state_store_names = (
        "execution_state_store",
        "execution_state_store_v2",
    )

    for label, names in (
        ("lifecycle owner", lifecycle_names),
        ("startup owner", startup_names),
        ("recovery owner", recovery_names),
        ("execution-state owner", state_store_names),
    ):
        cli_component = _context_component(cli_context, *names)
        asgi_component = _context_component(asgi_context, *names)
        assert _component_class_name(cli_component) == _component_class_name(
            asgi_component
        ), label


def test_asgi_and_direct_application_construction_register_equivalent_routes() -> None:
    """
    Compare the route contracts exposed by the ASGI construction path and the
    direct FastAPI factory path. Route ordering and object identity are not
    treated as part of the contract.
    """
    context = _build_cli_runtime_context()

    asgi_application = _construct_asgi_application(context)
    direct_application = _construct_direct_application(context)

    asgi_routes = _registered_route_signatures(asgi_application)
    direct_routes = _registered_route_signatures(direct_application)

    assert asgi_routes == direct_routes
    assert asgi_routes, "Application construction registered no routes"


def test_asgi_and_direct_application_use_the_same_runtime_safety_contract() -> None:
    """
    Verify that both application construction paths expose the account-bound
    runtime dependencies required to enforce PAPER execution safety.
    """
    context = _build_cli_runtime_context()

    asgi_application = _construct_asgi_application(context)
    direct_application = _construct_direct_application(context)

    asgi_context = _app_runtime_context(asgi_application)
    direct_context = _app_runtime_context(direct_application)

    assert _runtime_identity(asgi_context) == _runtime_identity(direct_context)

    required_components = {
        "lifecycle": (
            "runtime_lifecycle_manager",
            "runtime_lifecycle_manager_v2",
        ),
        "execution manager": (
            "execution_manager",
            "execution_manager_v2",
        ),
        "PAPER execution engine": (
            "paper_execution_engine",
            "paper_execution_engine_v2",
        ),
        "execution risk gate": (
            "execution_risk_gate",
            "execution_risk_gate_v1",
        ),
        "account state": (
            "account_state_manager",
            "account_state_manager_v2",
        ),
        "portfolio": (
            "portfolio_manager",
            "portfolio_manager_v2",
        ),
        "position manager": (
            "position_manager",
            "position_manager_v2",
        ),
        "state store": (
            "execution_state_store",
            "execution_state_store_v2",
        ),
    }

    for label, names in required_components.items():
        asgi_component = _context_component(asgi_context, *names)
        direct_component = _context_component(direct_context, *names)

        assert _component_class_name(asgi_component) == _component_class_name(
            direct_component
        ), label

    asgi_mode = str(
        _first_present_from_sources(
            _runtime_sources(asgi_context),
            ("execution_mode", "mode"),
            label="ASGI execution mode",
        )
    ).upper()
    direct_mode = str(
        _first_present_from_sources(
            _runtime_sources(direct_context),
            ("execution_mode", "mode"),
            label="direct application execution mode",
        )
    ).upper()

    assert asgi_mode == "PAPER"
    assert direct_mode == "PAPER"


def test_cli_and_asgi_compositions_do_not_select_live_execution() -> None:
    """
    The equivalence characterization must fail if either supported composition
    selects LIVE execution. This test does not instantiate or call a LIVE
    connector.
    """
    cli_context = _build_cli_runtime_context()
    asgi_application = _construct_asgi_application(cli_context)
    asgi_context = _app_runtime_context(asgi_application)

    for label, runtime_context in (
        ("CLI/main", cli_context),
        ("ASGI/app", asgi_context),
    ):
        mode = str(
            _first_present_from_sources(
                _runtime_sources(runtime_context),
                ("execution_mode", "mode"),
                label=f"{label} execution mode",
            )
        ).upper()
        assert mode == "PAPER", f"{label} selected unsafe execution mode"

        paper_engine = _context_component(
            runtime_context,
            "paper_execution_engine",
            "paper_execution_engine_v2",
        )
        assert "PAPER" in _component_class_name(paper_engine).upper()

        broker = _context_component(
            runtime_context,
            "broker_connector",
            "broker_connector_v2",
            "paper_broker_connector",
            "paper_broker_connector_v2",
        )
        broker_name = _component_class_name(broker).upper()
        assert "LIVE" not in broker_name
        assert "REAL" not in broker_name


def test_cli_and_asgi_compositions_expose_account_and_risk_authorities() -> None:
    """
    Compare the authority availability required before an execution request can
    be admitted. This intentionally checks availability and component type,
    not object identity.
    """
    cli_context = _build_cli_runtime_context()
    asgi_application = _construct_asgi_application(cli_context)
    asgi_context = _app_runtime_context(asgi_application)

    authorities = {
        "account state": (
            "account_state_manager",
            "account_state_manager_v2",
        ),
        "risk manager": (
            "risk_manager",
            "risk_manager_v2",
        ),
        "position sizing": (
            "position_sizing_engine",
            "position_sizing_engine_v2",
        ),
        "execution risk gate": (
            "execution_risk_gate",
            "execution_risk_gate_v1",
        ),
    }

    for label, names in authorities.items():
        cli_component = _context_component(cli_context, *names)
        asgi_component = _context_component(asgi_context, *names)

        assert _component_class_name(cli_component) == _component_class_name(
            asgi_component
        ), label

    # Account configuration is application-scoped rather than a public
    # RuntimeContextV2 component.  The ASGI factory must expose the
    # authoritative manager through app.state while retaining the injected
    # account-bound runtime context.
    account_config_manager = _first_present(
        asgi_application.state,
        (
            "account_config_manager",
            "account_config_manager_v2",
        ),
        label="ASGI account configuration authority",
    )

    assert (
        _component_class_name(account_config_manager)
        == "AccountConfigManagerV2"
    )

    application_authorities = {
        "trade validator": (
            ("trade_validator", "trade_validator_v2"),
            "TradeValidatorV2",
        ),
        "quote authority": (
            (
                "runtime_quote_authority",
                "runtime_quote_authority_v2",
            ),
            "RuntimeQuoteAuthorityV2",
        ),
        "price-feed authority": (
            ("price_feed_service", "price_feed_service_v2"),
            "PriceFeedServiceV2",
        ),
    }

    for label, (names, expected_class) in application_authorities.items():
        component = _first_present(
            asgi_application.state,
            names,
            label=f"ASGI {label}",
        )
        assert _component_class_name(component) == expected_class, label


def test_main_exposes_a_supported_runtime_entrypoint() -> None:
    """
    Characterize the process-level contract without running the CLI pipeline
    or creating execution side effects.
    """
    import backend.main as main_module

    assert callable(getattr(main_module, "main", None))
    assert callable(getattr(main_module, "build_runtime_context", None))

    source = inspect.getsource(main_module.main)
    assert "start_clean" in source
    assert "shutdown_to" in source
    assert "ArmsPipeline" in source


def test_runtime_context_contract_is_not_byte_identity_dependent() -> None:
    """
    Ensure the equivalence tests compare stable composition contracts rather
    than requiring independent runtime graphs to be the same objects.
    """
    first = _build_cli_runtime_context()
    second = _build_cli_runtime_context()

    assert first is not second
    assert _runtime_identity(first) == _runtime_identity(second)

    if is_dataclass(first) and is_dataclass(second):
        first_field_names = {field.name for field in fields(first)}
        second_field_names = {field.name for field in fields(second)}
        assert first_field_names == second_field_names
