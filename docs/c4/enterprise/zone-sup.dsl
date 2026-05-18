workspace "Zone SUPPORT" "C4 container view of the SUPPORT zone — each L2 capability is a container." {

    !identifiers hierarchical

    model {
        zone_SUP = softwareSystem "SUPPORT" "SUPPORT zone of the Reliever business capability model." {
            tags "capability-self" "zone:SUP"
            CAP_SUP_001_AUD = container "CAP.SUP.001.AUD" "Audit & Traceability" "stack-tbd" {
                tags "not-scaffolded" "tech:stack-tbd" "parent:CAP.SUP.001"
                properties {
                    "detail-view" "../CAP.SUP.001.AUD/workspace.dsl"
                    "parent" "CAP.SUP.001"
                }
            }
            CAP_SUP_001_CON = container "CAP.SUP.001.CON" "Consent Management" "stack-tbd" {
                tags "not-scaffolded" "tech:stack-tbd" "parent:CAP.SUP.001"
                properties {
                    "detail-view" "../CAP.SUP.001.CON/workspace.dsl"
                    "parent" "CAP.SUP.001"
                }
            }
            CAP_SUP_001_RET = container "CAP.SUP.001.RET" "Beneficiary Rights" "stack-tbd" {
                tags "not-scaffolded" "tech:stack-tbd" "parent:CAP.SUP.001"
                properties {
                    "detail-view" "../CAP.SUP.001.RET/workspace.dsl"
                    "parent" "CAP.SUP.001"
                }
            }
            CAP_SUP_002_BEN = container "CAP.SUP.002.BEN" "Beneficiary Identity Anchor" "python" {
                tags "implemented:mode-a" "tech:python" "parent:CAP.SUP.002"
                properties {
                    "detail-view" "../CAP.SUP.002.BEN/workspace.dsl"
                    "parent" "CAP.SUP.002"
                }
            }
        }

        CAP_BSP_002_ENR = softwareSystem "CAP.BSP.002.ENR" "External capability (other zone)." {
            tags "external-capability"
        }

        CAP_BSP_002_EXT = softwareSystem "CAP.BSP.002.EXT" "External capability (other zone)." {
            tags "external-capability"
        }
        CAP_BSP_002_ENR -> zone_SUP.CAP_SUP_001_CON "RVT.BSP.002.CASE_OPENED" "RabbitMQ" "upstream-event"
        CAP_BSP_002_EXT -> zone_SUP.CAP_SUP_001_RET "RVT.BSP.002.CASE_CLOSED" "RabbitMQ" "upstream-event"
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
