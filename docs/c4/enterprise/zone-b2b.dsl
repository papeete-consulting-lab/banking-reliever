workspace "Zone EXCHANGE_B2B" "C4 container view of the EXCHANGE_B2B zone — each L2 capability is a container." {

    !identifiers hierarchical

    model {
        zone_B2B = softwareSystem "EXCHANGE_B2B" "EXCHANGE_B2B zone of the Reliever business capability model." {
            tags "capability-self" "zone:B2B"
            CAP_B2B_001_CRD = container "CAP.B2B.001.CRD" "Dedicated Card Management" "stack-tbd" {
                tags "not-scaffolded" "tech:stack-tbd" "parent:CAP.B2B.001"
                properties {
                    "detail-view" "../CAP.B2B.001.CRD/workspace.dsl"
                    "parent" "CAP.B2B.001"
                }
            }
            CAP_B2B_001_FLW = container "CAP.B2B.001.FLW" "Financial Flow Management" "stack-tbd" {
                tags "not-scaffolded" "tech:stack-tbd" "parent:CAP.B2B.001"
                properties {
                    "detail-view" "../CAP.B2B.001.FLW/workspace.dsl"
                    "parent" "CAP.B2B.001"
                }
            }
            CAP_B2B_001_OBK = container "CAP.B2B.001.OBK" "Open Banking Integration" "stack-tbd" {
                tags "not-scaffolded" "tech:stack-tbd" "parent:CAP.B2B.001"
                properties {
                    "detail-view" "../CAP.B2B.001.OBK/workspace.dsl"
                    "parent" "CAP.B2B.001"
                }
            }
        }

        CAP_BSP_002_ENR = softwareSystem "CAP.BSP.002.ENR" "External capability (other zone)." {
            tags "external-capability"
        }

        CAP_BSP_001_TIE = softwareSystem "CAP.BSP.001.TIE" "External capability (other zone)." {
            tags "external-capability"
        }

        CAP_BSP_002_EXT = softwareSystem "CAP.BSP.002.EXT" "External capability (other zone)." {
            tags "external-capability"
        }

        CAP_BSP_004_ENV = softwareSystem "CAP.BSP.004.ENV" "External capability (other zone)." {
            tags "external-capability"
        }
        CAP_BSP_002_ENR -> zone_B2B.CAP_B2B_001_CRD "RVT.BSP.002.CASE_OPENED" "RabbitMQ" "upstream-event"
        CAP_BSP_001_TIE -> zone_B2B.CAP_B2B_001_CRD "RVT.BSP.001.TIER_UPGRADE_RECORDED" "RabbitMQ" "upstream-event"
        CAP_BSP_002_EXT -> zone_B2B.CAP_B2B_001_CRD "RVT.BSP.002.CASE_CLOSED" "RabbitMQ" "upstream-event"
        CAP_BSP_004_ENV -> zone_B2B.CAP_B2B_001_FLW "RVT.BSP.004.ENVELOPE_INITIALIZED" "RabbitMQ" "upstream-event"
        CAP_BSP_002_ENR -> zone_B2B.CAP_B2B_001_OBK "RVT.BSP.002.CASE_OPENED" "RabbitMQ" "upstream-event"
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
