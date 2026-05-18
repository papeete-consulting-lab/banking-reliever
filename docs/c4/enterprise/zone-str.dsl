workspace "Zone STEERING" "C4 container view of the STEERING zone — each L2 capability is a container." {

    !identifiers hierarchical

    model {
        zone_STR = softwareSystem "STEERING" "STEERING zone of the Reliever business capability model." {
            tags "capability-self" "zone:STR"
            CAP_STR_001_AUD = container "CAP.STR.001.AUD" "Programme Compliance Audit" "stack-tbd" {
                tags "not-scaffolded" "tech:stack-tbd" "parent:CAP.STR.001"
                properties {
                    "detail-view" "../CAP.STR.001.AUD/workspace.dsl"
                    "parent" "CAP.STR.001"
                }
            }
            CAP_STR_001_GOV = container "CAP.STR.001.GOV" "Programme Governance" "stack-tbd" {
                tags "not-scaffolded" "tech:stack-tbd" "parent:CAP.STR.001"
                properties {
                    "detail-view" "../CAP.STR.001.GOV/workspace.dsl"
                    "parent" "CAP.STR.001"
                }
            }
            CAP_STR_001_KPI = container "CAP.STR.001.KPI" "Performance Monitoring" "stack-tbd" {
                tags "not-scaffolded" "tech:stack-tbd" "parent:CAP.STR.001"
                properties {
                    "detail-view" "../CAP.STR.001.KPI/workspace.dsl"
                    "parent" "CAP.STR.001"
                }
            }
        }

        CAP_SUP_001_AUD = softwareSystem "CAP.SUP.001.AUD" "External capability (other zone)." {
            tags "external-capability"
        }

        CAP_DAT_001_MOD = softwareSystem "CAP.DAT.001.MOD" "External capability (other zone)." {
            tags "external-capability"
        }

        CAP_DAT_001_REP = softwareSystem "CAP.DAT.001.REP" "External capability (other zone)." {
            tags "external-capability"
        }
        CAP_SUP_001_AUD -> zone_STR.CAP_STR_001_AUD "RVT.SUP.001.TRACE_RECORDED" "RabbitMQ" "upstream-event"
        CAP_DAT_001_MOD -> zone_STR.CAP_STR_001_GOV "RVT.DAT.001.MODEL_SUBMITTED_TO_GOVERNANCE" "RabbitMQ" "upstream-event"
        CAP_DAT_001_REP -> zone_STR.CAP_STR_001_KPI "RVT.DAT.001.REPORT_AVAILABLE" "RabbitMQ" "upstream-event"
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
