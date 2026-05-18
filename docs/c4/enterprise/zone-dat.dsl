workspace "Zone DATA_ANALYTICS" "C4 container view of the DATA_ANALYTICS zone — each L2 capability is a container." {

    !identifiers hierarchical

    model {
        zone_DAT = softwareSystem "DATA_ANALYTICS" "DATA_ANALYTICS zone of the Reliever business capability model." {
            tags "capability-self" "zone:DAT"
            CAP_DAT_001_ING = container "CAP.DAT.001.ING" "Event Ingestion" "stack-tbd" {
                tags "not-scaffolded" "tech:stack-tbd" "parent:CAP.DAT.001"
                properties {
                    "detail-view" "../CAP.DAT.001.ING/workspace.dsl"
                    "parent" "CAP.DAT.001"
                }
            }
            CAP_DAT_001_MOD = container "CAP.DAT.001.MOD" "Score Analytics Model" "stack-tbd" {
                tags "not-scaffolded" "tech:stack-tbd" "parent:CAP.DAT.001"
                properties {
                    "detail-view" "../CAP.DAT.001.MOD/workspace.dsl"
                    "parent" "CAP.DAT.001"
                }
            }
            CAP_DAT_001_REP = container "CAP.DAT.001.REP" "Programme Reporting" "stack-tbd" {
                tags "not-scaffolded" "tech:stack-tbd" "parent:CAP.DAT.001"
                properties {
                    "detail-view" "../CAP.DAT.001.REP/workspace.dsl"
                    "parent" "CAP.DAT.001"
                }
            }
        }
        zone_DAT.CAP_DAT_001_ING -> zone_DAT.CAP_DAT_001_MOD "RVT.DAT.001.BATCH_AVAILABLE" "RabbitMQ" "upstream-event"
        zone_DAT.CAP_DAT_001_ING -> zone_DAT.CAP_DAT_001_REP "RVT.DAT.001.BATCH_AVAILABLE" "RabbitMQ" "upstream-event"
        zone_DAT.CAP_DAT_001_MOD -> zone_DAT.CAP_DAT_001_REP "RVT.DAT.001.MODEL_DEPLOYED_TO_PRODUCTION" "RabbitMQ" "upstream-event"
    }

    views {
        systemContext zone_DAT "Zone-Context" {
            include *
            autoLayout lr
        }
        container zone_DAT "Zone-Containers" {
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
