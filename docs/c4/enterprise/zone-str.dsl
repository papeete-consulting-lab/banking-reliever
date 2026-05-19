workspace "Zone — Steering" "C4 container view of the Steering zone — each L2 capability is a container." {

    !identifiers hierarchical

    model {
        zone_STR = softwareSystem "Steering" "Steering zone of the Reliever business capability model." {
            tags "capability-self" "zone:STR"
            properties {
                "zone-code" "STEERING"
            }
            CAP_STR_001_AUD = container "Programme Compliance Audit" "Verify the programme's overall regulatory compliance (banking, medical and social frameworks). Distinct from SUP.001.AUD (technical GDPR audit): STR.001.AUD certifies programme-level regulatory compliance, with the Compliance Officer as the principal actor." "stack-tbd" {
                tags "not-scaffolded" "tech:stack-tbd" "parent:CAP.STR.001"
                properties {
                    "capability-id" "CAP.STR.001.AUD"
                    "detail-view" "../CAP.STR.001.AUD/workspace.dsl"
                    "parent" "CAP.STR.001"
                }
            }
            CAP_STR_001_GOV = container "Programme Governance" "Define and evolve programme governance policies: eligibility rules, tier thresholds, co-decision protocols. Validates scoring model updates (ScoreModel.Updated from DAT.001.MOD) before any production deployment." "stack-tbd" {
                tags "not-scaffolded" "tech:stack-tbd" "parent:CAP.STR.001"
                properties {
                    "capability-id" "CAP.STR.001.GOV"
                    "detail-view" "../CAP.STR.001.GOV/workspace.dsl"
                    "parent" "CAP.STR.001"
                }
            }
            CAP_STR_001_KPI = container "Performance Monitoring" "Measure programme effectiveness at scale: progression rate, relapse rate, successful exit rate, perceived dignity. Consumes DAT.001.REP reports and produces ProgrammePerformance.Evaluated for governance decisions." "stack-tbd" {
                tags "not-scaffolded" "tech:stack-tbd" "parent:CAP.STR.001"
                properties {
                    "capability-id" "CAP.STR.001.KPI"
                    "detail-view" "../CAP.STR.001.KPI/workspace.dsl"
                    "parent" "CAP.STR.001"
                }
            }
        }

        CAP_SUP_001_AUD = softwareSystem "Audit & Traceability" "External capability (CAP.SUP.001.AUD) — emits business events consumed by this zone." {
            tags "external-capability"
            properties {
                "capability-id" "CAP.SUP.001.AUD"
            }
        }

        CAP_DAT_001_MOD = softwareSystem "Score Analytics Model" "External capability (CAP.DAT.001.MOD) — emits business events consumed by this zone." {
            tags "external-capability"
            properties {
                "capability-id" "CAP.DAT.001.MOD"
            }
        }

        CAP_DAT_001_REP = softwareSystem "Programme Reporting" "External capability (CAP.DAT.001.REP) — emits business events consumed by this zone." {
            tags "external-capability"
            properties {
                "capability-id" "CAP.DAT.001.REP"
            }
        }
        CAP_SUP_001_AUD -> zone_STR.CAP_STR_001_AUD "ACCESS LOGGED" "Business event subscription" "upstream-event"
        CAP_DAT_001_MOD -> zone_STR.CAP_STR_001_GOV "SCORE MODEL UPDATED" "Business event subscription" "upstream-event"
        CAP_DAT_001_REP -> zone_STR.CAP_STR_001_KPI "PROGRAM REPORT GENERATED" "Business event subscription" "upstream-event"
    }

    views {
        systemContext zone_STR "Zone-Context" {
            include *
            autoLayout lr
        }
        container zone_STR "Zone-Containers" {
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
