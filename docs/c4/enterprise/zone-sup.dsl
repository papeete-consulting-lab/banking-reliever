workspace "Zone — Support" "C4 container view of the Support zone — each L2 capability is a container." {

    !identifiers hierarchical

    model {
        zone_SUP = softwareSystem "Support" "Support zone of the Reliever business capability model." {
            tags "capability-self" "zone:SUP"
            properties {
                "zone-code" "SUPPORT"
            }
            CAP_SUP_001_AUD = container "Audit & Traceability" "Log all accesses and actions on beneficiary data, across all capabilities. Cross-cutting capability: 100% of beneficiary data accesses must produce DataAccess.Logged — a GDPR regulatory obligation." "stack-tbd" {
                tags "not-scaffolded" "tech:stack-tbd" "parent:CAP.SUP.001"
                properties {
                    "capability-id" "CAP.SUP.001.AUD"
                    "detail-view" "../CAP.SUP.001.AUD/workspace.dsl"
                    "parent" "CAP.SUP.001"
                }
            }
            CAP_SUP_001_CON = container "Consent Management" "Collect, store, manage and honour the beneficiary's GDPR consents for each type of data sharing. Consent.Granted is a blocking precondition for enrolment, open banking, and any prescriber consultation." "stack-tbd" {
                tags "not-scaffolded" "tech:stack-tbd" "parent:CAP.SUP.001"
                properties {
                    "capability-id" "CAP.SUP.001.CON"
                    "detail-view" "../CAP.SUP.001.CON/workspace.dsl"
                    "parent" "CAP.SUP.001"
                }
            }
            CAP_SUP_001_RET = container "Beneficiary Rights" "Process the beneficiary's GDPR rights requests (access, rectification, erasure, portability, objection) within the legal timeframe (1 month). Triggered notably by programme exit (BSP.002.EXT)." "stack-tbd" {
                tags "not-scaffolded" "tech:stack-tbd" "parent:CAP.SUP.001"
                properties {
                    "capability-id" "CAP.SUP.001.RET"
                    "detail-view" "../CAP.SUP.001.RET/workspace.dsl"
                    "parent" "CAP.SUP.001"
                }
            }
            CAP_SUP_002_BEN = container "Beneficiary Identity Anchor" "Hold the canonical beneficiary identity record, mint its UUIDv7 with a no-recycle-forever guarantee, and operate the GDPR Art. 17 pseudonymisation-at-anchor mechanics. Sole L2 of CAP.SUP.002. Relocated from CAP.REF.001 on 2026-05-15 per ADR-BCM-FUNC-0016 — golden record rule preserved." "python" {
                tags "implemented:mode-a" "tech:python" "parent:CAP.SUP.002"
                properties {
                    "capability-id" "CAP.SUP.002.BEN"
                    "detail-view" "../CAP.SUP.002.BEN/workspace.dsl"
                    "parent" "CAP.SUP.002"
                }
            }
        }

        CAP_BSP_002_ENR = softwareSystem "Enrolment" "External capability (CAP.BSP.002.ENR) — emits business events consumed by this zone." {
            tags "external-capability"
            properties {
                "capability-id" "CAP.BSP.002.ENR"
            }
        }

        CAP_BSP_002_EXT = softwareSystem "Programme Exit" "External capability (CAP.BSP.002.EXT) — emits business events consumed by this zone." {
            tags "external-capability"
            properties {
                "capability-id" "CAP.BSP.002.EXT"
            }
        }
        CAP_BSP_002_ENR -> zone_SUP.CAP_SUP_001_CON "BENEFICIARY ENROLLED" "Business event subscription" "upstream-event"
        CAP_BSP_002_EXT -> zone_SUP.CAP_SUP_001_RET "BENEFICIARY EXITED" "Business event subscription" "upstream-event"
    }

    views {
        systemContext zone_SUP "Zone-Context" {
            include *
            autoLayout lr
        }
        container zone_SUP "Zone-Containers" {
            include *
            autoLayout lr
        }
        styles {
            element "capability-self" {
                background "#1168bd"
                color "#ffffff"
                shape RoundedBox
            }
            element "external-capability" {
                background "#999999"
                color "#ffffff"
                shape RoundedBox
            }
            element "implemented:mode-a" {
                background "#2e7d32"
                color "#ffffff"
            }
            element "implemented:stub" {
                background "#fbc02d"
                color "#000000"
            }
            element "implemented:bff" {
                background "#0288d1"
                color "#ffffff"
            }
            element "implemented:frontend" {
                background "#7b1fa2"
                color "#ffffff"
            }
            element "not-scaffolded" {
                background "#bdbdbd"
                color "#000000"
                border Dashed
            }
            element "ddd:aggregate" {
                background "#ffd54f"
                color "#000000"
                shape Hexagon
            }
            element "ddd:read-model" {
                background "#a5d6a7"
                color "#000000"
                shape Cylinder
            }
            element "ddd:policy" {
                background "#ce93d8"
                color "#000000"
            }
            element "ddd:publisher" {
                background "#ffab91"
                color "#000000"
                shape Pipe
            }
            element "zone:BSP" {
                background "#e8eaf6"
            }
            element "zone:SUP" {
                background "#fce4ec"
            }
            element "zone:REF" {
                background "#f1f8e9"
            }
            element "zone:CHN" {
                background "#e0f7fa"
            }
            element "zone:CHANNEL" {
                background "#e0f7fa"
            }
            element "zone:B2B" {
                background "#fff8e1"
            }
            element "zone:DAT" {
                background "#ede7f6"
            }
            element "zone:STR" {
                background "#efebe9"
            }
            element "level:L1" {
                strokeWidth 4
            }
            element "level:L2" {
                strokeWidth 2
            }
            relationship "upstream-event" {
                dashed true
                color "#ff7043"
            }
            relationship "downstream-event" {
                dashed true
                color "#42a5f5"
            }
        }
    }
}
