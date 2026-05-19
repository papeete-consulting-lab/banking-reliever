workspace "Zone — Data Analytics" "C4 container view of the Data Analytics zone — each L2 capability is a container." {

    !identifiers hierarchical

    model {
        zone_DAT = softwareSystem "Data Analytics" "Data Analytics zone of the Reliever business capability model." {
            tags "capability-self" "zone:DAT"
            properties {
                "zone-code" "DATA_ANALYTICS"
            }
            CAP_DAT_001_ING = container "Event Ingestion" "Collect and consolidate in decoupled analytics mode all behavioural events produced by the programme (BSP.001, BSP.002, BSP.003, BSP.004) to feed the analytics pipelines. Strict separation from the operational transactional pipeline." "stack-tbd" {
                tags "not-scaffolded" "tech:stack-tbd" "parent:CAP.DAT.001"
                properties {
                    "capability-id" "CAP.DAT.001.ING"
                    "detail-view" "../CAP.DAT.001.ING/workspace.dsl"
                    "parent" "CAP.DAT.001"
                }
            }
            CAP_DAT_001_MOD = container "Score Analytics Model" "Analyse aggregated behavioural patterns, improve the scoring model and propose tier threshold updates. ScoreModel.Updated is sent to STR.001.GOV for validation — never directly to BSP.001.SCO, preventing any uncontrolled feedback loop." "stack-tbd" {
                tags "not-scaffolded" "tech:stack-tbd" "parent:CAP.DAT.001"
                properties {
                    "capability-id" "CAP.DAT.001.MOD"
                    "detail-view" "../CAP.DAT.001.MOD/workspace.dsl"
                    "parent" "CAP.DAT.001"
                }
            }
            CAP_DAT_001_REP = container "Programme Reporting" "Produce dashboards and monitoring reports on the overall effectiveness of the remediation programme: progression rate, relapse rate, exit rate. This data feeds STR.001.KPI for programme governance decisions." "stack-tbd" {
                tags "not-scaffolded" "tech:stack-tbd" "parent:CAP.DAT.001"
                properties {
                    "capability-id" "CAP.DAT.001.REP"
                    "detail-view" "../CAP.DAT.001.REP/workspace.dsl"
                    "parent" "CAP.DAT.001"
                }
            }
        }
        zone_DAT.CAP_DAT_001_ING -> zone_DAT.CAP_DAT_001_MOD "BEHAVIORAL DATA INGESTED" "Business event subscription" "upstream-event"
        zone_DAT.CAP_DAT_001_ING -> zone_DAT.CAP_DAT_001_REP "BEHAVIORAL DATA INGESTED" "Business event subscription" "upstream-event"
        zone_DAT.CAP_DAT_001_MOD -> zone_DAT.CAP_DAT_001_REP "SCORE MODEL UPDATED" "Business event subscription" "upstream-event"
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
