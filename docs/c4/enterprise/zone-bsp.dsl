workspace "Zone BUSINESS_SERVICE_PRODUCTION" "C4 container view of the BUSINESS_SERVICE_PRODUCTION zone — each L2 capability is a container." {

    !identifiers hierarchical

    model {
        zone_BSP = softwareSystem "BUSINESS_SERVICE_PRODUCTION" "BUSINESS_SERVICE_PRODUCTION zone of the Reliever business capability model." {
            tags "capability-self" "zone:BSP"
            CAP_BSP_001_ARB = container "CAP.BSP.001.ARB" "Prescriber Arbitration" "stack-tbd" {
                tags "not-scaffolded" "tech:stack-tbd" "parent:CAP.BSP.001"
                properties {
                    "detail-view" "../CAP.BSP.001.ARB/workspace.dsl"
                    "parent" "CAP.BSP.001"
                }
            }
            CAP_BSP_001_SCO = container "CAP.BSP.001.SCO" "Behavioural Scoring" "python" {
                tags "implemented:stub" "tech:python" "parent:CAP.BSP.001"
                properties {
                    "detail-view" "../CAP.BSP.001.SCO/workspace.dsl"
                    "parent" "CAP.BSP.001"
                }
            }
            CAP_BSP_001_SIG = container "CAP.BSP.001.SIG" "Signal Detection" "stack-tbd" {
                tags "not-scaffolded" "tech:stack-tbd" "parent:CAP.BSP.001"
                properties {
                    "detail-view" "../CAP.BSP.001.SIG/workspace.dsl"
                    "parent" "CAP.BSP.001"
                }
            }
            CAP_BSP_001_TIE = container "CAP.BSP.001.TIE" "Tier Management" "python" {
                tags "implemented:stub" "tech:python" "parent:CAP.BSP.001"
                properties {
                    "detail-view" "../CAP.BSP.001.TIE/workspace.dsl"
                    "parent" "CAP.BSP.001"
                }
            }
            CAP_BSP_002_CYC = container "CAP.BSP.002.CYC" "Lifecycle Monitoring" "stack-tbd" {
                tags "not-scaffolded" "tech:stack-tbd" "parent:CAP.BSP.002"
                properties {
                    "detail-view" "../CAP.BSP.002.CYC/workspace.dsl"
                    "parent" "CAP.BSP.002"
                }
            }
            CAP_BSP_002_ELI = container "CAP.BSP.002.ELI" "Eligibility" "stack-tbd" {
                tags "not-scaffolded" "tech:stack-tbd" "parent:CAP.BSP.002"
                properties {
                    "detail-view" "../CAP.BSP.002.ELI/workspace.dsl"
                    "parent" "CAP.BSP.002"
                }
            }
            CAP_BSP_002_ENR = container "CAP.BSP.002.ENR" "Enrolment" "stack-tbd" {
                tags "not-scaffolded" "tech:stack-tbd" "parent:CAP.BSP.002"
                properties {
                    "detail-view" "../CAP.BSP.002.ENR/workspace.dsl"
                    "parent" "CAP.BSP.002"
                }
            }
            CAP_BSP_002_EXT = container "CAP.BSP.002.EXT" "Programme Exit" "stack-tbd" {
                tags "not-scaffolded" "tech:stack-tbd" "parent:CAP.BSP.002"
                properties {
                    "detail-view" "../CAP.BSP.002.EXT/workspace.dsl"
                    "parent" "CAP.BSP.002"
                }
            }
            CAP_BSP_003_COD = container "CAP.BSP.003.COD" "Co-Decision" "stack-tbd" {
                tags "not-scaffolded" "tech:stack-tbd" "parent:CAP.BSP.003"
                properties {
                    "detail-view" "../CAP.BSP.003.COD/workspace.dsl"
                    "parent" "CAP.BSP.003"
                }
            }
            CAP_BSP_003_NOT = container "CAP.BSP.003.NOT" "Prescriber Notification & Communication" "stack-tbd" {
                tags "not-scaffolded" "tech:stack-tbd" "parent:CAP.BSP.003"
                properties {
                    "detail-view" "../CAP.BSP.003.NOT/workspace.dsl"
                    "parent" "CAP.BSP.003"
                }
            }
            CAP_BSP_003_ROL = container "CAP.BSP.003.ROL" "Prescriber Role Management" "stack-tbd" {
                tags "not-scaffolded" "tech:stack-tbd" "parent:CAP.BSP.003"
                properties {
                    "detail-view" "../CAP.BSP.003.ROL/workspace.dsl"
                    "parent" "CAP.BSP.003"
                }
            }
            CAP_BSP_004_ALT = container "CAP.BSP.004.ALT" "Behavioural Alerts" "stack-tbd" {
                tags "not-scaffolded" "tech:stack-tbd" "parent:CAP.BSP.004"
                properties {
                    "detail-view" "../CAP.BSP.004.ALT/workspace.dsl"
                    "parent" "CAP.BSP.004"
                }
            }
            CAP_BSP_004_AUT = container "CAP.BSP.004.AUT" "Transaction Authorisation" "stack-tbd" {
                tags "not-scaffolded" "tech:stack-tbd" "parent:CAP.BSP.004"
                properties {
                    "detail-view" "../CAP.BSP.004.AUT/workspace.dsl"
                    "parent" "CAP.BSP.004"
                }
            }
            CAP_BSP_004_ENV = container "CAP.BSP.004.ENV" "Budget Envelope Management" "stack-tbd" {
                tags "implemented:stub" "tech:stack-tbd" "parent:CAP.BSP.004"
                properties {
                    "detail-view" "../CAP.BSP.004.ENV/workspace.dsl"
                    "parent" "CAP.BSP.004"
                }
            }
        }

        CAP_CHN_002_ACT = softwareSystem "CAP.CHN.002.ACT" "External capability (other zone)." {
            tags "external-capability"
        }
        zone_BSP.CAP_BSP_001_TIE -> zone_BSP.CAP_BSP_001_ARB "RVT.BSP.001.OVERRIDE_ACTIVATED" "RabbitMQ" "upstream-event"
        zone_BSP.CAP_BSP_001_SCO -> zone_BSP.CAP_BSP_001_ARB "RVT.BSP.001.CURRENT_SCORE_RECOMPUTED" "RabbitMQ" "upstream-event"
        zone_BSP.CAP_BSP_004_AUT -> zone_BSP.CAP_BSP_001_SCO "RVT.BSP.004.PAYMENT_GRANTED" "RabbitMQ" "upstream-event"
        zone_BSP.CAP_BSP_001_SIG -> zone_BSP.CAP_BSP_001_SCO "RVT.BSP.001.RELAPSE_SIGNAL_QUALIFIED" "RabbitMQ" "upstream-event"
        zone_BSP.CAP_BSP_004_ENV -> zone_BSP.CAP_BSP_001_SIG "RVT.BSP.004.ENVELOPE_PERIOD_WITHOUT_CONSUMPTION" "RabbitMQ" "upstream-event"
        zone_BSP.CAP_BSP_004_AUT -> zone_BSP.CAP_BSP_001_SIG "RVT.BSP.004.PAYMENT_GRANTED" "RabbitMQ" "upstream-event"
        zone_BSP.CAP_BSP_001_SCO -> zone_BSP.CAP_BSP_001_TIE "RVT.BSP.001.SCORE_THRESHOLD_REACHED" "RabbitMQ" "upstream-event"
        zone_BSP.CAP_BSP_003_COD -> zone_BSP.CAP_BSP_001_TIE "RVT.BSP.003.CODECISION_OPENED" "RabbitMQ" "upstream-event"
        zone_BSP.CAP_BSP_002_ENR -> zone_BSP.CAP_BSP_002_CYC "RVT.BSP.002.CASE_OPENED" "RabbitMQ" "upstream-event"
        zone_BSP.CAP_BSP_001_SIG -> zone_BSP.CAP_BSP_002_CYC "RVT.BSP.001.RELAPSE_SIGNAL_QUALIFIED" "RabbitMQ" "upstream-event"
        zone_BSP.CAP_BSP_003_COD -> zone_BSP.CAP_BSP_002_ELI "RVT.BSP.003.CODECISION_OPENED" "RabbitMQ" "upstream-event"
        zone_BSP.CAP_BSP_002_ELI -> zone_BSP.CAP_BSP_002_ENR "RVT.BSP.002.ELIGIBILITY_RECORDED" "RabbitMQ" "upstream-event"
        zone_BSP.CAP_BSP_001_TIE -> zone_BSP.CAP_BSP_002_EXT "RVT.BSP.001.TIER_UPGRADE_RECORDED" "RabbitMQ" "upstream-event"
        CAP_CHN_002_ACT -> zone_BSP.CAP_BSP_003_COD "RVT.CHN.002.OVERRIDE_UX_INITIATED" "RabbitMQ" "upstream-event"
        zone_BSP.CAP_BSP_001_SIG -> zone_BSP.CAP_BSP_003_NOT "RVT.BSP.001.RELAPSE_SIGNAL_QUALIFIED" "RabbitMQ" "upstream-event"
        zone_BSP.CAP_BSP_001_TIE -> zone_BSP.CAP_BSP_003_NOT "RVT.BSP.001.TIER_UPGRADE_RECORDED" "RabbitMQ" "upstream-event"
        zone_BSP.CAP_BSP_004_ENV -> zone_BSP.CAP_BSP_003_NOT "RVT.BSP.004.ENVELOPE_PERIOD_WITHOUT_CONSUMPTION" "RabbitMQ" "upstream-event"
        zone_BSP.CAP_BSP_002_ENR -> zone_BSP.CAP_BSP_003_ROL "RVT.BSP.002.CASE_OPENED" "RabbitMQ" "upstream-event"
        zone_BSP.CAP_BSP_004_AUT -> zone_BSP.CAP_BSP_004_ALT "RVT.BSP.004.PAYMENT_BLOCKED" "RabbitMQ" "upstream-event"
        zone_BSP.CAP_BSP_001_TIE -> zone_BSP.CAP_BSP_004_AUT "RVT.BSP.001.TIER_UPGRADE_RECORDED" "RabbitMQ" "upstream-event"
        zone_BSP.CAP_BSP_002_ENR -> zone_BSP.CAP_BSP_004_ENV "RVT.BSP.002.CASE_OPENED" "RabbitMQ" "upstream-event"
        zone_BSP.CAP_BSP_001_TIE -> zone_BSP.CAP_BSP_004_ENV "RVT.BSP.001.TIER_UPGRADE_RECORDED" "RabbitMQ" "upstream-event"
    }

    views {
        systemContext zone_BSP "Zone-Context" {
            include *
            autoLayout lr
        }
        container zone_BSP "Zone-Containers" {
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
