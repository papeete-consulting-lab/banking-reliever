workspace "Zone CHANNEL" "C4 container view of the CHANNEL zone — each L2 capability is a container." {

    !identifiers hierarchical

    model {
        zone_CHN = softwareSystem "CHANNEL" "CHANNEL zone of the Reliever business capability model." {
            tags "capability-self" "zone:CHN"
            CAP_CHN_001_DSH = container "CAP.CHN.001.DSH" "Beneficiary Dashboard" "dotnet" {
                tags "implemented:channel-impl" "tech:dotnet" "parent:CAP.CHN.001"
                properties {
                    "detail-view" "../CAP.CHN.001.DSH/workspace.dsl"
                    "parent" "CAP.CHN.001"
                }
            }
            CAP_CHN_001_NOT = container "CAP.CHN.001.NOT" "Beneficiary Notifications" "stack-tbd" {
                tags "not-scaffolded" "tech:stack-tbd" "parent:CAP.CHN.001"
                properties {
                    "detail-view" "../CAP.CHN.001.NOT/workspace.dsl"
                    "parent" "CAP.CHN.001"
                }
            }
            CAP_CHN_001_PUR = container "CAP.CHN.001.PUR" "Purchase Assistance" "stack-tbd" {
                tags "not-scaffolded" "tech:stack-tbd" "parent:CAP.CHN.001"
                properties {
                    "detail-view" "../CAP.CHN.001.PUR/workspace.dsl"
                    "parent" "CAP.CHN.001"
                }
            }
            CAP_CHN_002_ACT = container "CAP.CHN.002.ACT" "Prescriber Actions" "stack-tbd" {
                tags "not-scaffolded" "tech:stack-tbd" "parent:CAP.CHN.002"
                properties {
                    "detail-view" "../CAP.CHN.002.ACT/workspace.dsl"
                    "parent" "CAP.CHN.002"
                }
            }
            CAP_CHN_002_REP = container "CAP.CHN.002.REP" "Prescriber Reporting" "stack-tbd" {
                tags "not-scaffolded" "tech:stack-tbd" "parent:CAP.CHN.002"
                properties {
                    "detail-view" "../CAP.CHN.002.REP/workspace.dsl"
                    "parent" "CAP.CHN.002"
                }
            }
            CAP_CHN_002_VIE = container "CAP.CHN.002.VIE" "Prescriber Beneficiary View" "stack-tbd" {
                tags "not-scaffolded" "tech:stack-tbd" "parent:CAP.CHN.002"
                properties {
                    "detail-view" "../CAP.CHN.002.VIE/workspace.dsl"
                    "parent" "CAP.CHN.002"
                }
            }
        }

        CAP_BSP_001_SCO = softwareSystem "CAP.BSP.001.SCO" "External capability (other zone)." {
            tags "external-capability"
        }

        CAP_BSP_001_TIE = softwareSystem "CAP.BSP.001.TIE" "External capability (other zone)." {
            tags "external-capability"
        }

        CAP_BSP_004_ENV = softwareSystem "CAP.BSP.004.ENV" "External capability (other zone)." {
            tags "external-capability"
        }

        CAP_BSP_004_AUT = softwareSystem "CAP.BSP.004.AUT" "External capability (other zone)." {
            tags "external-capability"
        }

        CAP_BSP_002_EXT = softwareSystem "CAP.BSP.002.EXT" "External capability (other zone)." {
            tags "external-capability"
        }

        CAP_BSP_004_ALT = softwareSystem "CAP.BSP.004.ALT" "External capability (other zone)." {
            tags "external-capability"
        }

        CAP_BSP_003_COD = softwareSystem "CAP.BSP.003.COD" "External capability (other zone)." {
            tags "external-capability"
        }

        CAP_BSP_001_SIG = softwareSystem "CAP.BSP.001.SIG" "External capability (other zone)." {
            tags "external-capability"
        }

        CAP_BSP_003_ROL = softwareSystem "CAP.BSP.003.ROL" "External capability (other zone)." {
            tags "external-capability"
        }
        CAP_BSP_001_SCO -> zone_CHN.CAP_CHN_001_DSH "RVT.BSP.001.CURRENT_SCORE_RECOMPUTED" "RabbitMQ" "upstream-event"
        CAP_BSP_001_TIE -> zone_CHN.CAP_CHN_001_DSH "RVT.BSP.001.TIER_UPGRADE_RECORDED" "RabbitMQ" "upstream-event"
        CAP_BSP_004_ENV -> zone_CHN.CAP_CHN_001_DSH "RVT.BSP.004.CONSUMPTION_RECORDED" "RabbitMQ" "upstream-event"
        CAP_BSP_004_AUT -> zone_CHN.CAP_CHN_001_NOT "RVT.BSP.004.PAYMENT_BLOCKED" "RabbitMQ" "upstream-event"
        CAP_BSP_001_TIE -> zone_CHN.CAP_CHN_001_NOT "RVT.BSP.001.TIER_UPGRADE_RECORDED" "RabbitMQ" "upstream-event"
        CAP_BSP_004_ENV -> zone_CHN.CAP_CHN_001_NOT "RVT.BSP.004.ENVELOPE_CAP_REACHED" "RabbitMQ" "upstream-event"
        CAP_BSP_002_EXT -> zone_CHN.CAP_CHN_001_NOT "RVT.BSP.002.STANDARD_APP_TRANSFER_RECORDED" "RabbitMQ" "upstream-event"
        CAP_BSP_004_AUT -> zone_CHN.CAP_CHN_001_PUR "RVT.BSP.004.PAYMENT_GRANTED" "RabbitMQ" "upstream-event"
        CAP_BSP_004_ALT -> zone_CHN.CAP_CHN_001_PUR "RVT.BSP.004.ALTERNATIVE_IDENTIFIED" "RabbitMQ" "upstream-event"
        CAP_BSP_003_COD -> zone_CHN.CAP_CHN_002_ACT "RVT.BSP.003.DECISION_COVALIDATED" "RabbitMQ" "upstream-event"
        zone_CHN.CAP_CHN_002_VIE -> zone_CHN.CAP_CHN_002_REP "RVT.CHN.002.CASE_VIEWED_BY_PRESCRIBER" "RabbitMQ" "upstream-event"
        CAP_BSP_001_SCO -> zone_CHN.CAP_CHN_002_VIE "RVT.BSP.001.CURRENT_SCORE_RECOMPUTED" "RabbitMQ" "upstream-event"
        CAP_BSP_001_TIE -> zone_CHN.CAP_CHN_002_VIE "RVT.BSP.001.TIER_UPGRADE_RECORDED" "RabbitMQ" "upstream-event"
        CAP_BSP_001_SIG -> zone_CHN.CAP_CHN_002_VIE "RVT.BSP.001.RELAPSE_SIGNAL_QUALIFIED" "RabbitMQ" "upstream-event"
        CAP_BSP_003_ROL -> zone_CHN.CAP_CHN_002_VIE "RVT.BSP.003.AUTHORIZATION_ACTIVATED" "RabbitMQ" "upstream-event"
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
