workspace "Zone — Channel" "C4 container view of the Channel zone — each L2 capability is a container." {

    !identifiers hierarchical

    model {
        zone_CHN = softwareSystem "Channel" "Channel zone of the Reliever business capability model." {
            tags "capability-self" "zone:CHN"
            properties {
                "zone-code" "CHANNEL"
            }
            CAP_CHN_001_DSH = container "Beneficiary Dashboard" "Expose to the beneficiary a synthetic view of their financial situation adapted to their tier: available balance, envelopes, transaction history. The interface is calibrated to encourage without patronising — dignity is a functional constraint." "dotnet" {
                tags "implemented:channel-impl" "tech:dotnet" "parent:CAP.CHN.001"
                properties {
                    "capability-id" "CAP.CHN.001.DSH"
                    "detail-view" "../CAP.CHN.001.DSH/workspace.dsl"
                    "parent" "CAP.CHN.001"
                }
            }
            CAP_CHN_001_NOT = container "Beneficiary Notifications" "Notify the beneficiary of relevant events in their journey: declined transaction, tier change, message from a prescriber, budget alert. Tone and content respect the dignity constraint." "stack-tbd" {
                tags "not-scaffolded" "tech:stack-tbd" "parent:CAP.CHN.001"
                properties {
                    "capability-id" "CAP.CHN.001.NOT"
                    "detail-view" "../CAP.CHN.001.NOT/workspace.dsl"
                    "parent" "CAP.CHN.001"
                }
            }
            CAP_CHN_001_PUR = container "Purchase Assistance" "Provide contextualised assistance at the point of purchase: budget availability check before payment, cheaper alternatives, price comparison. This capability is the UX manifestation of real-time behavioural control." "stack-tbd" {
                tags "not-scaffolded" "tech:stack-tbd" "parent:CAP.CHN.001"
                properties {
                    "capability-id" "CAP.CHN.001.PUR"
                    "detail-view" "../CAP.CHN.001.PUR/workspace.dsl"
                    "parent" "CAP.CHN.001"
                }
            }
            CAP_CHN_002_ACT = container "Prescriber Actions" "Allow authorised prescribers to take actions on a case: manual tier override, co-decision initiation, envelope rule adjustment. These actions are forwarded to BSP.003.COD or BSP.001.ARB." "stack-tbd" {
                tags "not-scaffolded" "tech:stack-tbd" "parent:CAP.CHN.002"
                properties {
                    "capability-id" "CAP.CHN.002.ACT"
                    "detail-view" "../CAP.CHN.002.ACT/workspace.dsl"
                    "parent" "CAP.CHN.002"
                }
            }
            CAP_CHN_002_REP = container "Prescriber Reporting" "Provide prescribers with aggregated monitoring reports on the beneficiary: score evolution, tier history, behavioural trends. Data comes from DAT.001.REP and is filtered by the prescriber's rights." "stack-tbd" {
                tags "not-scaffolded" "tech:stack-tbd" "parent:CAP.CHN.002"
                properties {
                    "capability-id" "CAP.CHN.002.REP"
                    "detail-view" "../CAP.CHN.002.REP/workspace.dsl"
                    "parent" "CAP.CHN.002"
                }
            }
            CAP_CHN_002_VIE = container "Prescriber Beneficiary View" "Expose to prescribers a filtered view of the beneficiary case according to their role and rights. A doctor does not see the same data as a banker. Access requires Consent.Granted (SUP.001.CON) as a precondition." "stack-tbd" {
                tags "not-scaffolded" "tech:stack-tbd" "parent:CAP.CHN.002"
                properties {
                    "capability-id" "CAP.CHN.002.VIE"
                    "detail-view" "../CAP.CHN.002.VIE/workspace.dsl"
                    "parent" "CAP.CHN.002"
                }
            }
        }

        CAP_BSP_001_SCO = softwareSystem "Behavioural Scoring" "External capability (CAP.BSP.001.SCO) — emits business events consumed by this zone." {
            tags "external-capability"
            properties {
                "capability-id" "CAP.BSP.001.SCO"
            }
        }

        CAP_BSP_001_TIE = softwareSystem "Tier Management" "External capability (CAP.BSP.001.TIE) — emits business events consumed by this zone." {
            tags "external-capability"
            properties {
                "capability-id" "CAP.BSP.001.TIE"
            }
        }

        CAP_BSP_004_ENV = softwareSystem "Budget Envelope Management" "External capability (CAP.BSP.004.ENV) — emits business events consumed by this zone." {
            tags "external-capability"
            properties {
                "capability-id" "CAP.BSP.004.ENV"
            }
        }

        CAP_BSP_004_AUT = softwareSystem "Transaction Authorisation" "External capability (CAP.BSP.004.AUT) — emits business events consumed by this zone." {
            tags "external-capability"
            properties {
                "capability-id" "CAP.BSP.004.AUT"
            }
        }

        CAP_BSP_002_EXT = softwareSystem "Programme Exit" "External capability (CAP.BSP.002.EXT) — emits business events consumed by this zone." {
            tags "external-capability"
            properties {
                "capability-id" "CAP.BSP.002.EXT"
            }
        }

        CAP_BSP_004_ALT = softwareSystem "Behavioural Alerts" "External capability (CAP.BSP.004.ALT) — emits business events consumed by this zone." {
            tags "external-capability"
            properties {
                "capability-id" "CAP.BSP.004.ALT"
            }
        }

        CAP_BSP_003_COD = softwareSystem "Co-Decision" "External capability (CAP.BSP.003.COD) — emits business events consumed by this zone." {
            tags "external-capability"
            properties {
                "capability-id" "CAP.BSP.003.COD"
            }
        }

        CAP_BSP_001_SIG = softwareSystem "Signal Detection" "External capability (CAP.BSP.001.SIG) — emits business events consumed by this zone." {
            tags "external-capability"
            properties {
                "capability-id" "CAP.BSP.001.SIG"
            }
        }

        CAP_BSP_003_ROL = softwareSystem "Prescriber Role Management" "External capability (CAP.BSP.003.ROL) — emits business events consumed by this zone." {
            tags "external-capability"
            properties {
                "capability-id" "CAP.BSP.003.ROL"
            }
        }
        CAP_BSP_001_SCO -> zone_CHN.CAP_CHN_001_DSH "SCORE RECOMPUTED" "Business event subscription" "upstream-event"
        CAP_BSP_001_TIE -> zone_CHN.CAP_CHN_001_DSH "TIER UPGRADED" "Business event subscription" "upstream-event"
        CAP_BSP_004_ENV -> zone_CHN.CAP_CHN_001_DSH "ENVELOPE CONSUMED" "Business event subscription" "upstream-event"
        CAP_BSP_004_AUT -> zone_CHN.CAP_CHN_001_NOT "TRANSACTION REFUSED" "Business event subscription" "upstream-event"
        CAP_BSP_001_TIE -> zone_CHN.CAP_CHN_001_NOT "TIER UPGRADED" "Business event subscription" "upstream-event"
        CAP_BSP_004_ENV -> zone_CHN.CAP_CHN_001_NOT "ENVELOPE DEPLETED" "Business event subscription" "upstream-event"
        CAP_BSP_002_EXT -> zone_CHN.CAP_CHN_001_NOT "BENEFICIARY TRANSFERRED TO STANDARD APP" "Business event subscription" "upstream-event"
        CAP_BSP_004_AUT -> zone_CHN.CAP_CHN_001_PUR "TRANSACTION AUTHORIZED, TRANSACTION REFUSED" "Business event subscription" "upstream-event"
        CAP_BSP_004_ALT -> zone_CHN.CAP_CHN_001_PUR "ALTERNATIVE PROPOSED" "Business event subscription" "upstream-event"
        CAP_BSP_003_COD -> zone_CHN.CAP_CHN_002_ACT "OVERRIDE COVALIDATED, OVERRIDE REFUSED" "Business event subscription" "upstream-event"
        zone_CHN.CAP_CHN_002_VIE -> zone_CHN.CAP_CHN_002_REP "CASE VIEWED" "Business event subscription" "upstream-event"
        CAP_BSP_001_SCO -> zone_CHN.CAP_CHN_002_VIE "SCORE RECOMPUTED" "Business event subscription" "upstream-event"
        CAP_BSP_001_TIE -> zone_CHN.CAP_CHN_002_VIE "TIER UPGRADED" "Business event subscription" "upstream-event"
        CAP_BSP_001_SIG -> zone_CHN.CAP_CHN_002_VIE "RELAPSE SIGNAL DETECTED" "Business event subscription" "upstream-event"
        CAP_BSP_003_ROL -> zone_CHN.CAP_CHN_002_VIE "ROLE ASSIGNED" "Business event subscription" "upstream-event"
    }

    views {
        systemContext zone_CHN "Zone-Context" {
            include *
            autoLayout lr
        }
        container zone_CHN "Zone-Containers" {
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
