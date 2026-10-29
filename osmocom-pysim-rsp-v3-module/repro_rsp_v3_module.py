# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 1oT OÜ. Authored by Hampus Hellsberg.

"""Minimal repro: pySim has no SGP.22 v3 RSP module.

pySim compiles one RSPDefinitions module, the SGP.22 v2 one. None of the
twenty-two BF-tagged request and response types SGP.22 v3.1 added -- ES10
(sections 5.7.3, 5.7.23-5.7.29), ES9+ (5.6.6, 5.6.7), ES11 (5.8.3) and
DeleteNotificationForDc (5.6.3) -- can be encoded or decoded with it. With the patch,
``pySim.esim.rsp.asn1_v3()`` returns the v3.1 module, every type round-trips
under its tag, and the two encodings whose meaning differs between the
versions are shown side by side. Exits 1 while any type is missing.

    python repro_rsp_v3_module.py
"""

from __future__ import annotations

import sys

import pySim
import pySim.esim.rsp as rsp

TID = bytes.fromhex("0102030405060708")
SIG = bytes(64)
ICCID = bytes.fromhex("98880221436587092143")
NOTIF = {"seqNumber": 1, "profileManagementOperation": (b"\x40", 2),
         "notificationAddress": "smdp.example.com", "iccid": ICCID}

# (type, tag SGP.22 v3.1 assigns, a minimal legal value)
TYPES_V3 = (
    ("EuiccConfiguredDataRequest", "bf3c", {}),
    ("EuiccConfiguredDataResponse", "bf3c", {"rootDsAddress": "smds.example.com"}),
    ("LoadRpmPackageRequest", "bf44", {
        "smdpSigned3": {"transactionId": TID, "rpmPackage": [{"rpmCommandDetails": ("enable", {"iccid": ICCID})}]},
        "smdpSignature3": SIG}),
    ("LoadRpmPackageResult", "bf44", ("loadRpmPackageResultNotSigned", {
        "transactionId": TID, "loadRpmPackageErrorCodeNotSigned": 4})),
    ("VerifySmdsResponseRequest", "bf45", {
        "smdsSigned2": {"transactionId": TID, "requestSpecificData": ("pushServiceRegistrationResult", {})},
        "smdsSignature2": SIG}),
    ("VerifySmdsResponseResponse", "bf45", ("verifySmdsResponseOk", None)),
    ("CheckEventRequest", "bf46", {"ecId": bytes(range(16)), "smdsAddress": "smds.example.com"}),
    ("CheckEventResponse", "bf46", ("checkEventOk", {"isPendingEvent": True})),
    ("AlertData", "bf4a", ("pendingOperationAlert", ("defaultSmdp", None))),
    ("VerifyDeviceChangeRequest", "bf4b", {
        "smdpSigned5": {"transactionId": TID, "deviceChangeResponse": ("deviceChangeData", {
            "iccid": ICCID, "activationCodeForDc": "1$smdp.example.com$ABC"})},
        "smdpSignature5": SIG}),
    ("VerifyDeviceChangeResponse", "bf4b", ("verifyDeviceChangeError", 8)),
    ("ConfirmDeviceChangeRequest", "bf4c", {
        "transactionId": TID, "prepareDeviceChangeResponse": ("prepareDeviceChangeResponseError", {
            "transactionId": TID, "downloadErrorCode": 127})}),
    ("ConfirmDeviceChangeResponse", "bf4c", ("confirmDeviceChangeError", 3)),
    ("PrepareDeviceChangeRequest", "bf4d", {
        "smdpSigned4": {"transactionId": TID, "ccRequiredFlag": False}, "smdpSignature4": SIG}),
    ("PrepareDeviceChangeResponse", "bf4d", ("prepareDeviceChangeResponseError", {
        "transactionId": TID, "downloadErrorCode": 127})),
    ("VerifySmdpResponseRequest", "bf60", {
        "smdpSigned6": {"transactionId": TID, "requestSpecificData": ("retryData", {
            "retryDelay": 5, "dcSessionId": b"\x01"})},
        "smdpSignature6": SIG}),
    ("VerifySmdpResponseResponse", "bf60", ("verifySmdpResponseOk", None)),
    ("CheckProgressRequest", "bf61", {"dcSessionId": b"\x01\x02"}),
    ("CheckProgressResponse", "bf61", ("checkProgressOk", {"retryDelay": 10})),
    ("VerifyProfileRecoveryRequest", "bf62", {
        "smdpSigned4": {"transactionId": TID, "ccRequiredFlag": True}, "smdpSignature4": SIG}),
    ("VerifyProfileRecoveryResponse", "bf62", ("verifyProfileRecoveryOk", None)),
    ("DeleteNotificationForDc", "bf63", {"notificationMetadata": NOTIF, "euiccNotificationSignature": SIG}),
)


def main() -> int:
    print(f"pySim from {pySim.__file__}")
    accessor = getattr(rsp, "asn1_v3", None)
    v3 = accessor() if accessor is not None else None
    print(f"pySim.esim.rsp.asn1_v3: {'present' if v3 is not None else 'absent'}\n")
    missing: list[str] = []
    for type_name, tag, value in TYPES_V3:
        in_v2 = type_name in rsp.asn1.types
        if v3 is None or type_name not in v3.types:
            print(f"  MISSING {type_name:30} (BF tag {tag[2:].upper()}){'  [in v2]' if in_v2 else ''}")
            missing.append(type_name)
            continue
        encoded = v3.encode(type_name, value)
        same = v3.decode(type_name, encoded) == value
        ok = encoded[:2] == bytes.fromhex(tag) and same
        print(f"  {'OK     ' if ok else 'BROKEN '} {type_name:30} {encoded[:2].hex().upper()} {len(encoded):3} bytes")
        if not ok:
            missing.append(type_name)

    if v3 is not None:
        print("\nSame bytes, different meaning per version:")
        devcap = bytes.fromhex("30058803020000")
        print(f"  DeviceCapabilities {devcap.hex()}: v2 {dict(rsp.asn1.decode('DeviceCapabilities', devcap))}"
              f" / v3.1 {dict(v3.decode('DeviceCapabilities', devcap))}")
        pir = rsp.asn1.encode("ProfileInstallationResultData", {
            "transactionId": TID, "notificationMetadata": NOTIF,
            "finalResult": ("errorResult", {"bppCommandId": 1, "errorReason": 1})})
        try:
            v3.decode("ProfileInstallationResultData", pir)
            outcome = "decodes"
        except Exception as error:                      # noqa: BLE001 - repro output
            outcome = f"{type(error).__name__}"
        print(f"  ProfileInstallationResultData without smdpOid: v2 decodes / v3.1 {outcome}")

    print()
    if len(missing) == 0:
        print(f"PASS: all {len(TYPES_V3)} BF-tagged SGP.22 v3.1 types encode and decode.")
        return 0
    print(f"FAIL: {len(missing)} of {len(TYPES_V3)} BF-tagged SGP.22 v3.1 types unavailable.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
