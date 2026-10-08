#!/usr/bin/env python3
"""Migrate RHDH Helm chart values from 1.x to 2.x structure.

Applies deterministic key mappings and flags ambiguous areas that need
AI-assisted or manual resolution. Original input files are never
modified — output goes to separate files (via -o) or stdout.

Usage:
    python3 migrate-chart-values.py values.yaml -o migrated.yaml [--report report.json]
    python3 migrate-chart-values.py values.yaml                   # prints to stdout
    cat values.yaml | python3 migrate-chart-values.py -            # reads from stdin
    python3 migrate-chart-values.py base.yaml prod.yaml --to 2.1 -o /tmp/migrated/

Multiple input files are migrated independently, preserving the
customer's file organization. When multiple files are given, -o must
be a directory (created if needed); each output keeps its original
filename.

Exit codes:
    0  All mappings deterministic (no review needed)
    1  Has ambiguous areas needing review (MIGRATION-REVIEW markers in output)
    2  Error (bad input, missing file, etc.)
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import sys
from typing import Any

try:
    import yaml
except ImportError:
    print(
        "Error: PyYAML is required. Install with: pip install pyyaml",
        file=sys.stderr,
    )
    sys.exit(2)


# ---------------------------------------------------------------------------
# Deterministic mapping tables
# ---------------------------------------------------------------------------
# Each entry: (old_dotpath, new_dotpath, notes)
# A new_dotpath of None means the value is removed (no 2.x equivalent).

DETERMINISTIC_MAPPINGS: list[tuple[str, str | None, str]] = [
    # Container image
    ("upstream.backstage.image.registry", "image.registry", ""),
    ("upstream.backstage.image.repository", "image.repository", ""),
    ("upstream.backstage.image.tag", "image.tag", ""),
    ("upstream.backstage.image.digest", "image.digest", ""),
    ("upstream.backstage.image.pullPolicy", "image.pullPolicy", ""),
    ("upstream.backstage.image.pullSecrets", "imagePullSecrets", "promoted to root"),
    # Chart-level overrides
    ("upstream.nameOverride", "nameOverride", "defaults to developer-hub"),
    ("upstream.fullnameOverride", "fullnameOverride", ""),
    ("upstream.commonLabels", "commonLabels", ""),
    ("upstream.commonAnnotations", "commonAnnotations", ""),
    ("upstream.extraDeploy", "extraDeploy", "can deploy additional resources alongside the chart (e.g., custom NetworkPolicy rules)"),
    # Global parameters
    ("global.clusterRouterBase", "openshift.clusterRouterBase", ""),
    ("global.host", "host", "promoted to root"),
    # App config
    ("upstream.backstage.appConfig", "appConfig", "entire tree flattened"),
    ("upstream.backstage.extraAppConfig", "extraAppConfig", ""),
    # Authentication (simple moves — existingSecret handled in ambiguous)
    ("global.auth.backend.enabled", "auth.backend.enabled", ""),
    ("global.auth.backend.value", "auth.backend.value", ""),
    # Dynamic plugins
    ("global.dynamic.includes", "dynamicPlugins.includes", ""),
    ("global.dynamic.plugins", "dynamicPlugins.plugins", ""),
    # Pod scheduling, replicas, metadata
    ("upstream.backstage.replicas", "replicaCount", "renamed"),
    ("upstream.backstage.revisionHistoryLimit", "revisionHistoryLimit", ""),
    ("upstream.backstage.strategy", "strategy", ""),
    ("upstream.backstage.annotations", "deploymentAnnotations", "renamed"),
    ("upstream.backstage.podAnnotations", "podAnnotations", ""),
    ("upstream.backstage.podLabels", "podLabels", ""),
    ("upstream.backstage.nodeSelector", "nodeSelector", ""),
    ("upstream.backstage.tolerations", "tolerations", ""),
    ("upstream.backstage.affinity", "affinity", ""),
    ("upstream.backstage.topologySpreadConstraints", "topologySpreadConstraints", ""),
    ("upstream.backstage.hostAliases", "hostAliases", ""),
    ("upstream.backstage.priorityClassName", "priorityClassName", ""),
    (
        "upstream.backstage.terminationGracePeriodSeconds",
        "terminationGracePeriodSeconds",
        "",
    ),
    ("upstream.backstage.lifecycleHooks", "lifecycleHooks", ""),
    # Service account
    ("upstream.serviceAccount.create", "serviceAccount.create", "defaults to false"),
    ("upstream.serviceAccount.name", "serviceAccount.name", ""),
    ("upstream.serviceAccount.annotations", "serviceAccount.annotations", ""),
    (
        "upstream.serviceAccount.automountServiceAccountToken",
        "serviceAccount.automount",
        "renamed",
    ),
    ("upstream.serviceAccount.labels", "serviceAccount.labels", ""),
    # Container command and env
    ("upstream.backstage.command", "commandOverride", "renamed"),
    ("upstream.backstage.extraEnvVars", "extraEnv", "renamed"),
    # Volumes and mounts
    ("upstream.backstage.extraVolumes", "extraVolumes", ""),
    ("upstream.backstage.extraVolumeMounts", "extraVolumeMounts", ""),
    # Sidecars
    ("upstream.backstage.extraContainers", "extraContainers", ""),
    # Security contexts and resources
    ("upstream.backstage.podSecurityContext", "podSecurityContext", ""),
    ("upstream.backstage.containerSecurityContext", "containerSecurityContext", ""),
    ("upstream.backstage.resources", "resources", ""),
    # Probes
    ("upstream.backstage.startupProbe", "startupProbe", ""),
    ("upstream.backstage.readinessProbe", "readinessProbe", ""),
    ("upstream.backstage.livenessProbe", "livenessProbe", ""),
    # Service
    ("upstream.service.type", "service.type", ""),
    ("upstream.service.ports.backend", "service.port", "flattened"),
    ("upstream.service.nodePorts.backend", "service.nodePort", "flattened"),
    ("upstream.service.extraPorts", "service.extraPorts", ""),
    ("upstream.service.clusterIP", "service.clusterIP", ""),
    ("upstream.service.loadBalancerIP", "service.loadBalancerIP", ""),
    ("upstream.service.loadBalancerSourceRanges", "service.loadBalancerSourceRanges", ""),
    (
        "upstream.service.externalTrafficPolicy",
        "service.externalTrafficPolicy",
        "",
    ),
    ("upstream.service.sessionAffinity", "service.sessionAffinity", ""),
    ("upstream.service.annotations", "service.annotations", ""),
    ("upstream.service.ipFamilyPolicy", "service.ipFamilyPolicy", ""),
    ("upstream.service.ipFamilies", "service.ipFamilies", ""),
    # OpenShift Route
    ("route.enabled", "openshift.route.enabled", ""),
    ("route.annotations", "openshift.route.annotations", ""),
    ("route.host", "openshift.route.host", ""),
    ("route.path", "openshift.route.path", ""),
    ("route.wildcardPolicy", "openshift.route.wildcardPolicy", ""),
    ("route.tls.enabled", "openshift.route.tls.enabled", ""),
    ("route.tls.termination", "openshift.route.tls.termination", ""),
    ("route.tls.certificate", "openshift.route.tls.certificate", ""),
    ("route.tls.key", "openshift.route.tls.key", ""),
    ("route.tls.caCertificate", "openshift.route.tls.caCertificate", ""),
    (
        "route.tls.destinationCACertificate",
        "openshift.route.tls.destinationCACertificate",
        "",
    ),
    (
        "route.tls.insecureEdgeTerminationPolicy",
        "openshift.route.tls.insecureEdgeTerminationPolicy",
        "",
    ),
    # Autoscaling
    ("upstream.backstage.autoscaling.enabled", "autoscaling.enabled", ""),
    ("upstream.backstage.autoscaling.minReplicas", "autoscaling.minReplicas", ""),
    (
        "upstream.backstage.autoscaling.maxReplicas",
        "autoscaling.maxReplicas",
        "default changed: 100 -> 3",
    ),
    (
        "upstream.backstage.autoscaling.targetCPUUtilizationPercentage",
        "autoscaling.targetCPUUtilizationPercentage",
        "",
    ),
    (
        "upstream.backstage.autoscaling.targetMemoryUtilizationPercentage",
        "autoscaling.targetMemoryUtilizationPercentage",
        "",
    ),
    # PDB
    ("upstream.backstage.pdb.create", "podDisruptionBudget.create", ""),
    ("upstream.backstage.pdb.minAvailable", "podDisruptionBudget.minAvailable", ""),
    (
        "upstream.backstage.pdb.maxUnavailable",
        "podDisruptionBudget.maxUnavailable",
        "",
    ),
    # HTTPRoute
    ("upstream.httpRoute.enabled", "httpRoute.enabled", ""),
    ("upstream.httpRoute.labels", "httpRoute.labels", ""),
    ("upstream.httpRoute.annotations", "httpRoute.annotations", ""),
    ("upstream.httpRoute.parentRefs", "httpRoute.parentRefs", ""),
    ("upstream.httpRoute.hostnames", "httpRoute.hostnames", ""),
    ("upstream.httpRoute.rules", "httpRoute.rules", ""),
    # Catalog index
    ("global.catalogIndex.image.registry", "catalogIndex.image.registry", ""),
    ("global.catalogIndex.image.repository", "catalogIndex.image.repository", ""),
    ("global.catalogIndex.image.tag", "catalogIndex.image.tag", ""),
    ("global.catalogIndex.extraImages", "catalogIndex.extraImages", ""),
    # PostgreSQL
    ("upstream.postgresql.enabled", "postgresql.enabled", ""),
    ("upstream.postgresql.postgresqlDataDir", "postgresql.postgresqlDataDir", ""),
    (
        "upstream.postgresql.serviceBindings.enabled",
        "postgresql.serviceBindings.enabled",
        "",
    ),
    (
        "upstream.postgresql.image",
        "postgresql.image",
        "default changed: PostgreSQL 15 -> 18",
    ),
    ("upstream.postgresql.auth", "postgresql.auth", ""),
    ("upstream.postgresql.primary", "postgresql.primary", ""),
    # Metrics
    (
        "upstream.metrics.serviceMonitor.enabled",
        "metrics.serviceMonitor.enabled",
        "",
    ),
    ("upstream.metrics.serviceMonitor.path", "metrics.serviceMonitor.path", ""),
    ("upstream.metrics.serviceMonitor.port", "metrics.serviceMonitor.port", ""),
    (
        "upstream.metrics.serviceMonitor.interval",
        "metrics.serviceMonitor.interval",
        "",
    ),
    (
        "upstream.metrics.serviceMonitor.labels",
        "metrics.serviceMonitor.labels",
        "",
    ),
    (
        "upstream.metrics.serviceMonitor.annotations",
        "metrics.serviceMonitor.annotations",
        "",
    ),
    # Removed values
    ("upstream.backstage.installDir", None, "hardcoded in new chart"),
    (
        "upstream.backstage.containerPorts.backend",
        None,
        "hardcoded to 7007",
    ),
    ("upstream.diagnosticMode", None, "not supported in new chart"),
    ("test.injectTestNpmrcSecret", None, "removed"),
]

# Ambiguous area detector prefixes — keys starting with these trigger review
AMBIGUOUS_PREFIXES: dict[str, str] = {
    "upstream.ingress": "ingress",
    "upstream.backstage.args": "args",
    "upstream.backstage.extraEnvVarsSecrets": "extraEnvFrom",
    "upstream.backstage.extraEnvVarsCM": "extraEnvFrom",
    "upstream.backstage.initContainers": "initContainers",
    "upstream.networkPolicy": "networkPolicy",
    "global.lightspeed": "intelligentAssistant",
    "global.auth.backend.existingSecret": "authSecret",
    "orchestrator.sonataflowPlatform.externalDBsecretRef": "orchestrator",
    "orchestrator.sonataflowPlatform.externalDBName": "orchestrator",
    "orchestrator.sonataflowPlatform.externalDBHost": "orchestrator",
    "orchestrator.sonataflowPlatform.externalDBPort": "orchestrator",
    "orchestrator.sonataflowPlatform.initContainerImage": "orchestrator",
    "orchestrator.sonataflowPlatform.createDBJobImage": "orchestrator",
    "orchestrator.sonataflowPlatform.dataIndexImage": "orchestrator",
    "orchestrator.sonataflowPlatform.jobServiceImage": "orchestrator",
    "orchestrator.sonataflowPlatform.dbCreationJobBackoffLimit": "orchestrator",
    "orchestrator.sonataflowPlatform.dbCreationJobTTLSecondsAfterFinished": "orchestrator",
    "orchestrator.sonataflowPlatform.dbCreationJobActiveDeadlineSeconds": "orchestrator",
}

AMBIGUOUS_DESCRIPTIONS: dict[str, str] = {
    "ingress": (
        "Ingress structure changed from single host/path to array of host objects. "
        "extraHosts merge into hosts[]; TLS becomes a list of structured entries."
    ),
    "args": (
        "upstream.backstage.args maps to either extraArgs (appends after system --config flags, preferred) "
        "or argsOverride (replaces all arguments). Review which is appropriate for your use case."
    ),
    "extraEnvFrom": (
        "extraEnvVarsSecrets and extraEnvVarsCM both map to extraEnvFrom. "
        "Format changes from simple name strings to secretRef/configMapRef entries."
    ),
    "initContainers": (
        "System init containers are no longer raw arrays. Configure install-dynamic-plugins "
        "via dynamicPlugins.initContainer.*; use preInitContainers/extraInitContainers for custom ones."
    ),
    "networkPolicy": (
        "upstream.networkPolicy.* has no equivalent. The new chart always deploys default-deny "
        "NetworkPolicies. Review your connectivity requirements and add rules as needed. "
        "You can use extraDeploy to deploy custom NetworkPolicy resources alongside the chart."
    ),
    "intelligentAssistant": (
        "Lightspeed rebranded to Intelligent Assistant with significant structural changes: "
        "image string splits, configMap array restructuring, secret handling changes, "
        "removed RAG init container. ref:// plugin format available as convenience shorthand "
        "(oci:// still fully supported)."
    ),
    "authSecret": (
        "global.auth.backend.existingSecret (string) becomes auth.backend.existingSecretRef "
        "with name and key fields. The key defaults to 'backend-secret'."
    ),
    "orchestrator": (
        "Orchestrator fields restructured: flat DB fields nest under externalDB.*, "
        "image strings split into registry/repository/tag, job fields nest under dbCreationJob.*."
    ),
}


# ---------------------------------------------------------------------------
# YAML helpers
# ---------------------------------------------------------------------------

def deep_get(data: dict, dotpath: str) -> tuple[Any, bool]:
    """Get a value from a nested dict by dotted path. Returns (value, found)."""
    keys = dotpath.split(".")
    current = data
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return None, False
        current = current[key]
    return current, True


def deep_set(data: dict, dotpath: str, value: Any) -> None:
    """Set a value in a nested dict by dotted path, creating intermediate dicts."""
    keys = dotpath.split(".")
    current = data
    for key in keys[:-1]:
        if key not in current or not isinstance(current[key], dict):
            current[key] = {}
        current = current[key]
    current[keys[-1]] = value


def deep_delete(data: dict, dotpath: str) -> bool:
    """Delete a value from a nested dict by dotted path. Returns True if deleted."""
    keys = dotpath.split(".")
    current = data
    parents: list[tuple[dict, str]] = []
    for key in keys[:-1]:
        if not isinstance(current, dict) or key not in current:
            return False
        parents.append((current, key))
        current = current[key]
    if not isinstance(current, dict) or keys[-1] not in current:
        return False
    del current[keys[-1]]
    # Clean up empty parent dicts
    for parent, key in reversed(parents):
        if isinstance(parent[key], dict) and not parent[key]:
            del parent[key]
        else:
            break
    return True


def flatten_keys(data: dict, prefix: str = "") -> list[str]:
    """Return all dotted key paths in a nested dict."""
    result = []
    for key, value in data.items():
        full = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            result.extend(flatten_keys(value, full))
        else:
            result.append(full)
    return result


# ---------------------------------------------------------------------------
# Ambiguous area handlers
# ---------------------------------------------------------------------------

def handle_ingress(old_data: dict) -> tuple[dict, list[str]]:
    """Transform 1.x ingress to 2.x structure."""
    ingress_data, found = deep_get(old_data, "upstream.ingress")
    if not found or not isinstance(ingress_data, dict):
        return {}, []

    new_ingress: dict[str, Any] = {}
    warnings: list[str] = []

    for simple_key in ("enabled", "className", "annotations"):
        if simple_key in ingress_data:
            new_ingress[simple_key] = ingress_data[simple_key]

    hosts: list[dict] = []
    primary_host = ingress_data.get("host")
    primary_path = ingress_data.get("path", "/")
    if primary_host:
        hosts.append({
            "host": primary_host,
            "paths": [{"path": primary_path}],
        })

    extra_hosts = ingress_data.get("extraHosts", [])
    if isinstance(extra_hosts, list):
        for eh in extra_hosts:
            if isinstance(eh, dict):
                hosts.append({
                    "host": eh.get("name", eh.get("host", "")),
                    "paths": [{"path": eh.get("path", "/")}],
                })

    if hosts:
        new_ingress["hosts"] = hosts

    tls_entries: list[dict] = []
    old_tls = ingress_data.get("tls", {})
    if isinstance(old_tls, dict):
        if old_tls.get("enabled") and old_tls.get("secretName"):
            tls_hosts = [primary_host] if primary_host else []
            tls_entries.append({
                "hosts": tls_hosts,
                "secretName": old_tls["secretName"],
            })
            if not primary_host:
                warnings.append(
                    "TLS enabled but no primary host found to associate with the TLS entry"
                )
    elif isinstance(old_tls, list):
        tls_entries.extend(old_tls)

    extra_tls = ingress_data.get("extraTls", [])
    if isinstance(extra_tls, list):
        tls_entries.extend(extra_tls)

    if tls_entries:
        new_ingress["tls"] = tls_entries

    return new_ingress, warnings


def handle_extra_env_from(old_data: dict) -> list[dict] | None:
    """Merge extraEnvVarsSecrets and extraEnvVarsCM into extraEnvFrom."""
    entries: list[dict] = []

    secrets, found_s = deep_get(old_data, "upstream.backstage.extraEnvVarsSecrets")
    if found_s and isinstance(secrets, list):
        for name in secrets:
            if isinstance(name, str):
                entries.append({"secretRef": {"name": name}})
            elif isinstance(name, dict):
                entries.append(name)

    cms, found_c = deep_get(old_data, "upstream.backstage.extraEnvVarsCM")
    if found_c and isinstance(cms, list):
        for name in cms:
            if isinstance(name, str):
                entries.append({"configMapRef": {"name": name}})
            elif isinstance(name, dict):
                entries.append(name)

    return entries if entries else None


def handle_args(old_data: dict) -> tuple[str, Any, str]:
    """Decide whether args should map to extraArgs or argsOverride."""
    args, found = deep_get(old_data, "upstream.backstage.args")
    if not found:
        return "", None, ""

    if isinstance(args, list) and any(
        isinstance(a, str) and "--config" in a for a in args
    ):
        return "argsOverride", args, (
            "Your args contain --config flags, suggesting you manage config loading manually. "
            "Using argsOverride (replaces all arguments). Verify this is correct."
        )

    return "extraArgs", args, (
        "Using extraArgs (appends after system --config flags). "
        "If you need full argument control, change to argsOverride."
    )


def handle_auth_secret(old_data: dict) -> dict | None:
    """Transform existingSecret string to existingSecretRef object."""
    secret, found = deep_get(old_data, "global.auth.backend.existingSecret")
    if not found:
        return None
    if isinstance(secret, str):
        return {"name": secret, "key": "backend-secret"}
    return None


def split_image_string(image: str) -> dict[str, str]:
    """Split a container image string into registry/repository/tag components."""
    result: dict[str, str] = {}
    tag_part = ""
    repo_part = image

    if ":" in image and not image.startswith("sha256:"):
        repo_part, tag_part = image.rsplit(":", 1)
        result["tag"] = tag_part

    parts = repo_part.split("/")
    if len(parts) >= 3:
        result["registry"] = parts[0]
        result["repository"] = "/".join(parts[1:])
    elif len(parts) == 2:
        if "." in parts[0] or ":" in parts[0]:
            result["registry"] = parts[0]
            result["repository"] = parts[1]
        else:
            result["repository"] = repo_part
    else:
        result["repository"] = repo_part

    return result


def handle_lightspeed(old_data: dict) -> tuple[dict, list[str]]:
    """Transform global.lightspeed to intelligentAssistant."""
    ls_data, found = deep_get(old_data, "global.lightspeed")
    if not found or not isinstance(ls_data, dict):
        return {}, []

    ia: dict[str, Any] = {}
    warnings: list[str] = []

    if "enabled" in ls_data:
        ia["enabled"] = ls_data["enabled"]

    if "plugins" in ls_data:
        ia["plugins"] = ls_data["plugins"]
        warnings.append(
            "The new chart supports ref:// as a convenience shorthand for default catalog plugins. "
            "Your existing oci:// references still work — no migration needed, but you may "
            "optionally simplify them to ref:// format."
        )

    sidecar = ls_data.get("sidecar", {})
    if isinstance(sidecar, dict):
        core: dict[str, Any] = {}
        if "image" in sidecar and isinstance(sidecar["image"], str):
            core["image"] = split_image_string(sidecar["image"])
        for old_key, new_key in [
            ("resources", "resources"),
            ("securityContext", "securityContext"),
            ("command", "commandOverride"),
            ("args", "argsOverride"),
            ("env", "extraEnv"),
            ("imagePullPolicy", "imagePullPolicy"),
        ]:
            if old_key in sidecar:
                core[new_key] = sidecar[old_key]
        if core:
            ia["core"] = core

    rv = ls_data.get("runtimeVolume", {})
    if isinstance(rv, dict):
        new_rv: dict[str, Any] = {}
        for k in ("type", "emptyDir", "persistentVolumeClaim"):
            if k in rv:
                new_rv[k] = rv[k]
        if new_rv:
            ia["runtimeVolume"] = new_rv

    config_maps = ls_data.get("configMaps", [])
    if isinstance(config_maps, list) and config_maps:
        config: dict[str, Any] = {}
        for cm in config_maps:
            if not isinstance(cm, dict) or "name" not in cm:
                continue
            name = cm["name"]
            if "stack" in name.lower():
                config.setdefault("stack", {})["existingConfigMap"] = name
            elif "profile" in name.lower():
                config.setdefault("profile", {})["existingConfigMap"] = name
        if len(config_maps) > len(config):
            warnings.append(
                "Could not automatically classify all Lightspeed configMaps. "
                "Review intelligentAssistant.config entries."
            )
        if config:
            ia["config"] = config

    secret = ls_data.get("secret", {})
    if isinstance(secret, dict) and secret.get("name"):
        ia["existingSecret"] = secret["name"]
        warnings.append(
            "The new chart does NOT create a placeholder secret. "
            "You must create the secret independently before upgrading."
        )

    removed_keys = [
        "initContainer", "ragVolume", "secret.optional",
        "sidecar.name", "sidecar.portName", "sidecar.containerPort",
        "runtimeVolume.name", "runtimeVolume.mountPath",
    ]
    for rk in removed_keys:
        val, exists = deep_get(ls_data, rk)
        if exists:
            warnings.append(f"global.lightspeed.{rk} is removed in 2.x (hardcoded or no longer needed)")

    return ia, warnings


def handle_orchestrator(old_data: dict) -> tuple[dict, list[str]]:
    """Transform orchestrator flat fields to nested structure."""
    orch, found = deep_get(old_data, "orchestrator.sonataflowPlatform")
    if not found or not isinstance(orch, dict):
        return {}, []

    new_sfp: dict[str, Any] = {}
    warnings: list[str] = []

    ext_db: dict[str, Any] = {}
    db_field_map = {
        "externalDBsecretRef": "existingSecret",
        "externalDBName": "name",
        "externalDBHost": "host",
        "externalDBPort": "port",
    }
    for old_key, new_key in db_field_map.items():
        if old_key in orch:
            ext_db[new_key] = orch[old_key]
    if ext_db:
        new_sfp["externalDB"] = ext_db

    db_job: dict[str, Any] = {}
    for img_key in ("initContainerImage", "createDBJobImage"):
        if img_key in orch and isinstance(orch[img_key], str):
            parsed = split_image_string(orch[img_key])
            if "image" in db_job and db_job["image"] != parsed:
                warnings.append(
                    f"initContainerImage and createDBJobImage differ but merge into "
                    f"dbCreationJob.image. Using {img_key} value."
                )
            db_job["image"] = parsed

    job_field_map = {
        "dbCreationJobBackoffLimit": "backoffLimit",
        "dbCreationJobTTLSecondsAfterFinished": "ttlSecondsAfterFinished",
        "dbCreationJobActiveDeadlineSeconds": "activeDeadlineSeconds",
    }
    for old_key, new_key in job_field_map.items():
        if old_key in orch:
            db_job[new_key] = orch[old_key]
    if db_job:
        new_sfp["dbCreationJob"] = db_job

    for img_field, nest_key in [
        ("dataIndexImage", "dataIndex"),
        ("jobServiceImage", "jobService"),
    ]:
        if img_field in orch and isinstance(orch[img_field], str):
            new_sfp[nest_key] = {"image": split_image_string(orch[img_field])}

    # Preserve any keys not covered by the migration
    migrated_keys = set(db_field_map) | {"initContainerImage", "createDBJobImage"} | set(job_field_map) | {"dataIndexImage", "jobServiceImage"}
    for k, v in orch.items():
        if k not in migrated_keys:
            new_sfp[k] = v

    return new_sfp, warnings


def handle_init_containers(old_data: dict) -> tuple[dict, list[str]]:
    """Transform initContainers array to structured config."""
    containers, found = deep_get(old_data, "upstream.backstage.initContainers")
    if not found or not isinstance(containers, list):
        return {}, []

    result: dict[str, Any] = {}
    warnings: list[str] = []
    extra: list[dict] = []

    for i, container in enumerate(containers):
        if not isinstance(container, dict):
            extra.append(container)
            continue
        name = container.get("name", "")
        if "dynamic-plugin" in name or "install-dynamic" in name or i == 0:
            dp_init: dict[str, Any] = {}
            for k in ("resources", "securityContext"):
                if k in container:
                    dp_init[k] = container[k]
            if "env" in container:
                dp_init["extraEnv"] = container["env"]
            if dp_init:
                result["dynamicPlugins"] = {"initContainer": dp_init}
        else:
            extra.append(container)

    if extra:
        result["extraInitContainers"] = extra
        warnings.append(
            f"Moved {len(extra)} custom init container(s) to extraInitContainers. "
            "If any should run before system init containers, move them to preInitContainers."
        )

    return result, warnings


# ---------------------------------------------------------------------------
# Core migration engine
# ---------------------------------------------------------------------------

class MigrationReport:
    """Tracks all transformations and review items."""

    def __init__(self) -> None:
        self.applied: list[dict[str, str]] = []
        self.removed: list[dict[str, str]] = []
        self.review: list[dict[str, str]] = []
        self.warnings: list[str] = []
        self.unknown_upstream_keys: list[str] = []

    @property
    def has_review_items(self) -> bool:
        return bool(self.review) or bool(self.unknown_upstream_keys)

    def to_dict(self) -> dict:
        return {
            "applied": self.applied,
            "removed": self.removed,
            "review": self.review,
            "warnings": self.warnings,
            "unknown_upstream_keys": self.unknown_upstream_keys,
            "summary": {
                "total_deterministic": len(self.applied),
                "total_removed": len(self.removed),
                "total_review": len(self.review),
                "total_warnings": len(self.warnings),
                "total_unknown": len(self.unknown_upstream_keys),
                "needs_review": self.has_review_items,
            },
        }


def migrate(old_data: dict) -> tuple[dict, MigrationReport]:
    """Apply all migrations to old_data and return (new_data, report)."""
    data = copy.deepcopy(old_data)
    new_data: dict[str, Any] = {}
    report = MigrationReport()

    # Track which old paths we've handled
    handled_prefixes: set[str] = set()

    # 1. Apply deterministic mappings
    for old_path, new_path, notes in DETERMINISTIC_MAPPINGS:
        value, found = deep_get(data, old_path)
        if not found:
            continue
        if new_path is None:
            report.removed.append({
                "old": old_path,
                "notes": notes,
            })
        else:
            deep_set(new_data, new_path, value)
            report.applied.append({
                "old": old_path,
                "new": new_path,
                "notes": notes,
            })
        deep_delete(data, old_path)
        handled_prefixes.add(old_path)

    # 2. Handle ambiguous areas
    # Ingress
    ingress_data, found = deep_get(data, "upstream.ingress")
    if found:
        new_ingress, ing_warnings = handle_ingress(data)
        if new_ingress:
            existing = new_data.get("ingress", {})
            existing.update(new_ingress)
            new_data["ingress"] = existing
            report.review.append({
                "area": "ingress",
                "description": AMBIGUOUS_DESCRIPTIONS["ingress"],
                "original_keys": [
                    k for k in flatten_keys({"upstream": {"ingress": ingress_data}})
                ],
            })
            report.warnings.extend(ing_warnings)
        deep_delete(data, "upstream.ingress")
        handled_prefixes.add("upstream.ingress")

    # Args
    args_key, args_value, args_note = handle_args(data)
    if args_key and args_value is not None:
        deep_set(new_data, args_key, args_value)
        report.review.append({
            "area": "args",
            "description": args_note,
            "mapped_to": args_key,
        })
        deep_delete(data, "upstream.backstage.args")
        handled_prefixes.add("upstream.backstage.args")

    # ExtraEnvFrom
    env_from = handle_extra_env_from(data)
    if env_from is not None:
        existing_env_from = new_data.get("extraEnvFrom", [])
        if isinstance(existing_env_from, list):
            existing_env_from.extend(env_from)
        else:
            existing_env_from = env_from
        new_data["extraEnvFrom"] = existing_env_from
        report.review.append({
            "area": "extraEnvFrom",
            "description": AMBIGUOUS_DESCRIPTIONS["extraEnvFrom"],
        })
        deep_delete(data, "upstream.backstage.extraEnvVarsSecrets")
        deep_delete(data, "upstream.backstage.extraEnvVarsCM")
        handled_prefixes.add("upstream.backstage.extraEnvVarsSecrets")
        handled_prefixes.add("upstream.backstage.extraEnvVarsCM")

    # Auth secret
    auth_ref = handle_auth_secret(data)
    if auth_ref is not None:
        deep_set(new_data, "auth.backend.existingSecretRef", auth_ref)
        report.review.append({
            "area": "authSecret",
            "description": AMBIGUOUS_DESCRIPTIONS["authSecret"],
        })
        deep_delete(data, "global.auth.backend.existingSecret")
        handled_prefixes.add("global.auth.backend.existingSecret")

    # Init containers
    init_result, init_warnings = handle_init_containers(data)
    if init_result:
        for k, v in init_result.items():
            if k in new_data and isinstance(new_data[k], dict) and isinstance(v, dict):
                new_data[k].update(v)
            else:
                new_data[k] = v
        report.review.append({
            "area": "initContainers",
            "description": AMBIGUOUS_DESCRIPTIONS["initContainers"],
        })
        report.warnings.extend(init_warnings)
        deep_delete(data, "upstream.backstage.initContainers")
        handled_prefixes.add("upstream.backstage.initContainers")

    # NetworkPolicy
    np_data, found = deep_get(data, "upstream.networkPolicy")
    if found:
        report.review.append({
            "area": "networkPolicy",
            "description": AMBIGUOUS_DESCRIPTIONS["networkPolicy"],
            "removed_keys": flatten_keys({"upstream": {"networkPolicy": np_data}}),
        })
        deep_delete(data, "upstream.networkPolicy")
        handled_prefixes.add("upstream.networkPolicy")

    # Lightspeed / Intelligent Assistant
    ia_data, ia_warnings = handle_lightspeed(data)
    if ia_data:
        new_data["intelligentAssistant"] = ia_data
        report.review.append({
            "area": "intelligentAssistant",
            "description": AMBIGUOUS_DESCRIPTIONS["intelligentAssistant"],
        })
        report.warnings.extend(ia_warnings)
        deep_delete(data, "global.lightspeed")
        handled_prefixes.add("global.lightspeed")

    # Orchestrator
    orch_result, orch_warnings = handle_orchestrator(data)
    if orch_result:
        deep_set(new_data, "orchestrator.sonataflowPlatform", orch_result)
        report.review.append({
            "area": "orchestrator",
            "description": AMBIGUOUS_DESCRIPTIONS["orchestrator"],
        })
        report.warnings.extend(orch_warnings)
        # Remove only the migrated keys from orchestrator
        for key in list(AMBIGUOUS_PREFIXES):
            if key.startswith("orchestrator."):
                deep_delete(data, key)
        handled_prefixes.add("orchestrator.sonataflowPlatform")

    # 2b. Post-migration warnings for image and air-gapped behavior
    # Warn about digest/tag precedence when user sets image tags
    image_tag_paths = [
        "image.tag", "postgresql.image.tag", "catalogIndex.image.tag",
        "intelligentAssistant.core.image.tag",
    ]
    for tag_path in image_tag_paths:
        tag_val, has_tag = deep_get(new_data, tag_path)
        if has_tag and tag_val:
            digest_path = tag_path.rsplit(".", 1)[0] + ".digest"
            digest_val, has_digest = deep_get(new_data, digest_path)
            if not has_digest or digest_val:
                report.warnings.append(
                    f"{tag_path} is set but {digest_path} is not cleared. "
                    f"The downstream chart ships images with explicit digests by default. "
                    f"When both are set, the chart renders tag@digest, which can fail to "
                    f"resolve at pull time if they don't match (the chart's default digest "
                    f"is merged by Helm). Either set `{digest_path}: \"\"` to clear the "
                    f"default, or set it to the correct digest for your tag."
                )

    # Warn about air-gapped plugin limitation
    global_registry, has_gr = deep_get(new_data, "global.imageRegistry")
    if has_gr and global_registry:
        report.warnings.append(
            "global.imageRegistry is set (air-gapped/disconnected environment). "
            "Note: this applies to chart-managed container images only, NOT to dynamic "
            "plugin references (oci:// or ref:// in dynamicPlugins.plugins). Plugin OCI "
            "images must be mirrored separately and their references updated individually."
        )

    # 3. Pass through remaining keys
    remaining_keys = flatten_keys(data)
    for key in remaining_keys:
        is_upstream = key.startswith(("upstream.", "global."))
        if is_upstream:
            already_handled = any(
                key == p or key.startswith(p + ".") for p in handled_prefixes
            )
            if not already_handled:
                report.unknown_upstream_keys.append(key)

        value, _ = deep_get(data, key)
        if not any(key == p or key.startswith(p + ".") for p in handled_prefixes):
            deep_set(new_data, key, value)

    return new_data, report


# ---------------------------------------------------------------------------
# YAML output with review markers
# ---------------------------------------------------------------------------

def add_review_comments(yaml_str: str, report: MigrationReport) -> str:
    """Insert MIGRATION-REVIEW comments into the YAML output."""
    lines = yaml_str.split("\n")
    header_comments: list[str] = []

    if report.review:
        header_comments.append(
            "# ================================================================"
        )
        header_comments.append(
            "# MIGRATION-REVIEW: This file was auto-generated from 1.x values."
        )
        header_comments.append(
            f"# {len(report.applied)} keys migrated deterministically."
        )
        header_comments.append(
            f"# {len(report.review)} area(s) flagged for review (search for MIGRATION-REVIEW)."
        )
        if report.removed:
            header_comments.append(
                f"# {len(report.removed)} key(s) removed (no 2.x equivalent)."
            )
        if report.unknown_upstream_keys:
            header_comments.append(
                f"# {len(report.unknown_upstream_keys)} unknown upstream key(s) carried over with warnings."
            )
        header_comments.append(
            "# ================================================================"
        )
        header_comments.append("")

    for item in report.review:
        area = item["area"]
        desc = item["description"]
        # Find the YAML key that corresponds to this area
        area_key_map = {
            "ingress": "ingress:",
            "args": ("extraArgs:", "argsOverride:"),
            "extraEnvFrom": "extraEnvFrom:",
            "initContainers": ("dynamicPlugins:", "extraInitContainers:", "preInitContainers:"),
            "networkPolicy": None,
            "intelligentAssistant": "intelligentAssistant:",
            "authSecret": "auth:",
            "orchestrator": "orchestrator:",
        }
        search_keys = area_key_map.get(area)
        if search_keys is None:
            header_comments.append(f"# MIGRATION-REVIEW [{area}]: {desc}")
            header_comments.append("")
            continue

        if isinstance(search_keys, str):
            search_keys = (search_keys,)

        for sk in search_keys:
            for i, line in enumerate(lines):
                stripped = line.lstrip()
                if stripped.startswith(sk):
                    indent = line[: len(line) - len(stripped)]
                    comment = f"{indent}# MIGRATION-REVIEW [{area}]: {desc}"
                    lines.insert(i, comment)
                    break

    for key in report.unknown_upstream_keys:
        top_key = key.split(".")[0] + ":"
        for i, line in enumerate(lines):
            if line.lstrip().startswith(top_key):
                indent = line[: len(line) - len(line.lstrip())]
                comment = f"{indent}# MIGRATION-REVIEW [unknown]: '{key}' is an upstream key not in the mapping tables. Verify it is still valid."
                if i > 0 and "MIGRATION-REVIEW [unknown]" not in lines[i - 1]:
                    lines.insert(i, comment)
                break

    if report.removed:
        lines.append("")
        lines.append("# Removed values (no 2.x equivalent):")
        for item in report.removed:
            lines.append(f"#   {item['old']} — {item['notes']}")

    return "\n".join(header_comments + lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _read_yaml(path: str) -> dict:
    """Read and parse a YAML file, returning the top-level mapping."""
    if path == "-":
        raw = sys.stdin.read()
    else:
        with open(path) as f:
            raw = f.read()
    data = yaml.safe_load(raw)
    if not isinstance(data, dict):
        raise ValueError(f"{path}: input must be a YAML mapping (dict)")
    return data


def _migrate_one(
    input_path: str,
    old_data: dict,
    output_path: str | None,
    json_mode: bool,
    target_version: str | None = None,
) -> tuple[dict, MigrationReport]:
    """Migrate a single values file and write output. Returns (report_dict, report)."""
    new_data, report = migrate(old_data)

    if json_mode:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        yaml_str = yaml.dump(
            new_data,
            default_flow_style=False,
            sort_keys=False,
            allow_unicode=True,
        )
        output_str = add_review_comments(yaml_str, report)
        if target_version:
            header = f"# Migrated from: {input_path} (target: RHDH {target_version})\n"
        else:
            header = f"# Migrated from: {input_path}\n"
        output_str = header + output_str

        if output_path:
            with open(output_path, "w") as f:
                f.write(output_str)
            print(
                f"Wrote migrated values to {output_path}",
                file=sys.stderr,
            )
        else:
            print(output_str)

    return report.to_dict(), report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Migrate RHDH Helm chart values from 1.x to 2.x structure.",
    )
    parser.add_argument(
        "input",
        nargs="+",
        help="Path(s) to 1.x values.yaml file(s) (use '-' for stdin). "
        "Multiple files are migrated independently, preserving file "
        "separation. Your original files are never modified.",
    )
    parser.add_argument(
        "-o", "--output",
        help="Output path: a file when migrating a single input, or a "
        "directory (created if needed) when migrating multiple inputs. "
        "Defaults to stdout for a single input.",
    )
    parser.add_argument(
        "--report",
        help="Path to write the JSON migration report",
    )
    parser.add_argument(
        "--to",
        metavar="VERSION",
        help="Target RHDH version (e.g. 2.1). Used in multi-file output "
        "filenames (base.yaml -> base-2.1.yaml). Falls back to "
        "'-migrated' suffix if omitted.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output the report as JSON to stdout instead of YAML",
    )
    args = parser.parse_args()

    inputs: list[str] = args.input
    multi = len(inputs) > 1

    if multi and not args.output:
        print(
            "Error: -o/--output directory is required when migrating "
            "multiple files",
            file=sys.stderr,
        )
        return 2

    if multi and "-" in inputs:
        print(
            "Error: stdin ('-') cannot be combined with other input files",
            file=sys.stderr,
        )
        return 2

    if multi and args.output:
        os.makedirs(args.output, exist_ok=True)

    any_review = False
    all_reports: list[dict] = []

    for input_path in inputs:
        try:
            old_data = _read_yaml(input_path)
        except (FileNotFoundError, PermissionError) as e:
            print(f"Error: {e}", file=sys.stderr)
            return 2
        except yaml.YAMLError as e:
            print(f"Error parsing YAML: {e}", file=sys.stderr)
            return 2
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 2

        if multi:
            base = os.path.basename(input_path)
            name, ext = os.path.splitext(base)
            suffix = args.to if args.to else "migrated"
            out_path = os.path.join(args.output, f"{name}-{suffix}{ext}")
        else:
            out_path = args.output

        report_dict, report = _migrate_one(
            input_path, old_data, out_path, args.json, args.to,
        )
        report_dict["file"] = input_path
        all_reports.append(report_dict)
        if report.has_review_items:
            any_review = True

    # Write combined report
    combined_report = all_reports[0] if len(all_reports) == 1 else {
        "files": all_reports,
        "summary": {
            "total_files": len(all_reports),
            "total_deterministic": sum(
                r["summary"]["total_deterministic"] for r in all_reports
            ),
            "total_removed": sum(
                r["summary"]["total_removed"] for r in all_reports
            ),
            "total_review": sum(
                r["summary"]["total_review"] for r in all_reports
            ),
            "total_warnings": sum(
                r["summary"]["total_warnings"] for r in all_reports
            ),
            "total_unknown": sum(
                r["summary"]["total_unknown"] for r in all_reports
            ),
            "needs_review": any_review,
        },
    }
    if args.report:
        with open(args.report, "w") as f:
            json.dump(combined_report, f, indent=2)
        print(f"Wrote report to {args.report}", file=sys.stderr)

    # Print summary to stderr
    if multi:
        s = combined_report["summary"]
        print(
            f"\nMigration summary ({s['total_files']} files): "
            f"{s['total_deterministic']} keys migrated, "
            f"{s['total_removed']} removed, "
            f"{s['total_review']} areas for review, "
            f"{s['total_unknown']} unknown upstream keys",
            file=sys.stderr,
        )
    else:
        summary = all_reports[0]["summary"]
        print(
            f"\nMigration summary: "
            f"{summary['total_deterministic']} keys migrated, "
            f"{summary['total_removed']} removed, "
            f"{summary['total_review']} areas for review, "
            f"{summary['total_unknown']} unknown upstream keys",
            file=sys.stderr,
        )

    return 1 if any_review else 0


if __name__ == "__main__":
    sys.exit(main())
