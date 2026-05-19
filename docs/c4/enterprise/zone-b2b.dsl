workspace "Zone — Exchange B2b" "C4 container view of the Exchange B2b zone — each L2 capability is a container." {

    !identifiers hierarchical

    model {
        zone_B2B = softwareSystem "Exchange B2b" "Exchange B2b zone of the Reliever business capability model." {
            tags "capability-self" "zone:B2B"
            properties {
                "zone-code" "EXCHANGE_B2B"
            }
            CAP_B2B_001_CRD = container "Dedicated Card Management" "Drive the complete lifecycle of the Reliever dedicated card — issuance, activation, suspension, termination — in liaison with an approved issuing partner. Card usage rules (limits, categories) are synchronised with the current tier." "stack-tbd" {
                tags "not-scaffolded" "tech:stack-tbd" "parent:CAP.B2B.001"
                properties {
                    "capability-id" "CAP.B2B.001.CRD"
                    "detail-view" "../CAP.B2B.001.CRD/workspace.dsl"
                    "parent" "CAP.B2B.001"
                }
            }
            CAP_B2B_001_FLW = container "Financial Flow Management" "Orchestrate the funding of the dedicated card from the beneficiary's main account, ensure flow reconciliation and handle anomalies. Triggered by envelope events from BSP.004.ENV." "stack-tbd" {
                tags "not-scaffolded" "tech:stack-tbd" "parent:CAP.B2B.001"
                properties {
                    "capability-id" "CAP.B2B.001.FLW"
                    "detail-view" "../CAP.B2B.001.FLW/workspace.dsl"
                    "parent" "CAP.B2B.001"
                }
            }
            CAP_B2B_001_OBK = container "Open Banking Integration" "Access and refresh the beneficiary's main account financial data via open banking APIs (PSD2). Requires prior Consent.Granted. Makes Reliever independent of inter-bank agreements." "stack-tbd" {
                tags "not-scaffolded" "tech:stack-tbd" "parent:CAP.B2B.001"
                properties {
                    "capability-id" "CAP.B2B.001.OBK"
                    "detail-view" "../CAP.B2B.001.OBK/workspace.dsl"
                    "parent" "CAP.B2B.001"
                }
            }
        }

        CAP_BSP_002_ENR = softwareSystem "Enrolment" "External capability (CAP.BSP.002.ENR) — emits business events consumed by this zone." {
            tags "external-capability"
            properties {
                "capability-id" "CAP.BSP.002.ENR"
            }
        }

        CAP_BSP_001_TIE = softwareSystem "Tier Management" "External capability (CAP.BSP.001.TIE) — emits business events consumed by this zone." {
            tags "external-capability"
            properties {
                "capability-id" "CAP.BSP.001.TIE"
            }
        }

        CAP_BSP_002_EXT = softwareSystem "Programme Exit" "External capability (CAP.BSP.002.EXT) — emits business events consumed by this zone." {
            tags "external-capability"
            properties {
                "capability-id" "CAP.BSP.002.EXT"
            }
        }

        CAP_BSP_004_ENV = softwareSystem "Budget Envelope Management" "External capability (CAP.BSP.004.ENV) — emits business events consumed by this zone." {
            tags "external-capability"
            properties {
                "capability-id" "CAP.BSP.004.ENV"
            }
        }
        CAP_BSP_002_ENR -> zone_B2B.CAP_B2B_001_CRD "BENEFICIARY ENROLLED" "Business event subscription" "upstream-event"
        CAP_BSP_001_TIE -> zone_B2B.CAP_B2B_001_CRD "TIER DOWNGRADED, TIER UPGRADED" "Business event subscription" "upstream-event"
        CAP_BSP_002_EXT -> zone_B2B.CAP_B2B_001_CRD "BENEFICIARY EXITED" "Business event subscription" "upstream-event"
        CAP_BSP_004_ENV -> zone_B2B.CAP_B2B_001_FLW "ENVELOPE ALLOCATED, ENVELOPE DEPLETED" "Business event subscription" "upstream-event"
        CAP_BSP_002_ENR -> zone_B2B.CAP_B2B_001_OBK "BENEFICIARY ENROLLED" "Business event subscription" "upstream-event"
    }

    views {
        systemContext zone_B2B "Zone-Context" {
            include *
            autoLayout lr
        }
        container zone_B2B "Zone-Containers" {
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
