workspace "Reliever — Enterprise C4" "System landscape — every L2 capability grouped by zone." {

    !identifiers hierarchical

    model {
        beneficiary = person "Beneficiary" "Recipient of the Reliever programme."
        prescriber = person "Prescriber" "Social worker or programme prescriber."
        regulator = person "Regulator" "Programme governance, compliance auditor."
        partner_bank = softwareSystem "Partner bank" "Financial institution providing card and payment rails." {
            tags "external-system"
        }

        reliever = softwareSystem "Reliever" "Financial-inclusion programme: behavioural remediation, autonomy tiers, prescriber co-decision." {
            tags "capability-self"
            zone_BSP = container "BUSINESS_SERVICE_PRODUCTION" "BUSINESS_SERVICE_PRODUCTION zone" "group" {
                tags "zone:BSP" "capability-self"
                CAP_BSP_001_ARB = component "CAP.BSP.001.ARB" "Prescriber Arbitration" "stack-tbd" {
                    tags "not-scaffolded" "tech:stack-tbd" "level:L2"
                }
                CAP_BSP_001_SCO = component "CAP.BSP.001.SCO" "Behavioural Scoring" "python" {
                    tags "implemented:stub" "tech:python" "level:L2"
                }
                CAP_BSP_001_SIG = component "CAP.BSP.001.SIG" "Signal Detection" "stack-tbd" {
                    tags "not-scaffolded" "tech:stack-tbd" "level:L2"
                }
                CAP_BSP_001_TIE = component "CAP.BSP.001.TIE" "Tier Management" "python" {
                    tags "implemented:stub" "tech:python" "level:L2"
                }
                CAP_BSP_002_CYC = component "CAP.BSP.002.CYC" "Lifecycle Monitoring" "stack-tbd" {
                    tags "not-scaffolded" "tech:stack-tbd" "level:L2"
                }
                CAP_BSP_002_ELI = component "CAP.BSP.002.ELI" "Eligibility" "stack-tbd" {
                    tags "not-scaffolded" "tech:stack-tbd" "level:L2"
                }
                CAP_BSP_002_ENR = component "CAP.BSP.002.ENR" "Enrolment" "stack-tbd" {
                    tags "not-scaffolded" "tech:stack-tbd" "level:L2"
                }
                CAP_BSP_002_EXT = component "CAP.BSP.002.EXT" "Programme Exit" "stack-tbd" {
                    tags "not-scaffolded" "tech:stack-tbd" "level:L2"
                }
                CAP_BSP_003_COD = component "CAP.BSP.003.COD" "Co-Decision" "stack-tbd" {
                    tags "not-scaffolded" "tech:stack-tbd" "level:L2"
                }
                CAP_BSP_003_NOT = component "CAP.BSP.003.NOT" "Prescriber Notification & Communication" "stack-tbd" {
                    tags "not-scaffolded" "tech:stack-tbd" "level:L2"
                }
                CAP_BSP_003_ROL = component "CAP.BSP.003.ROL" "Prescriber Role Management" "stack-tbd" {
                    tags "not-scaffolded" "tech:stack-tbd" "level:L2"
                }
                CAP_BSP_004_ALT = component "CAP.BSP.004.ALT" "Behavioural Alerts" "stack-tbd" {
                    tags "not-scaffolded" "tech:stack-tbd" "level:L2"
                }
                CAP_BSP_004_AUT = component "CAP.BSP.004.AUT" "Transaction Authorisation" "stack-tbd" {
                    tags "not-scaffolded" "tech:stack-tbd" "level:L2"
                }
                CAP_BSP_004_ENV = component "CAP.BSP.004.ENV" "Budget Envelope Management" "stack-tbd" {
                    tags "implemented:stub" "tech:stack-tbd" "level:L2"
                }
            }
            zone_CHN = container "CHANNEL" "CHANNEL zone" "group" {
                tags "zone:CHN" "capability-self"
                CAP_CHN_001_DSH = component "CAP.CHN.001.DSH" "Beneficiary Dashboard" "dotnet" {
                    tags "implemented:channel-impl" "tech:dotnet" "level:L2"
                }
                CAP_CHN_001_NOT = component "CAP.CHN.001.NOT" "Beneficiary Notifications" "stack-tbd" {
                    tags "not-scaffolded" "tech:stack-tbd" "level:L2"
                }
                CAP_CHN_001_PUR = component "CAP.CHN.001.PUR" "Purchase Assistance" "stack-tbd" {
                    tags "not-scaffolded" "tech:stack-tbd" "level:L2"
                }
                CAP_CHN_002_ACT = component "CAP.CHN.002.ACT" "Prescriber Actions" "stack-tbd" {
                    tags "not-scaffolded" "tech:stack-tbd" "level:L2"
                }
                CAP_CHN_002_REP = component "CAP.CHN.002.REP" "Prescriber Reporting" "stack-tbd" {
                    tags "not-scaffolded" "tech:stack-tbd" "level:L2"
                }
                CAP_CHN_002_VIE = component "CAP.CHN.002.VIE" "Prescriber Beneficiary View" "stack-tbd" {
                    tags "not-scaffolded" "tech:stack-tbd" "level:L2"
                }
            }
            zone_DAT = container "DATA_ANALYTICS" "DATA_ANALYTICS zone" "group" {
                tags "zone:DAT" "capability-self"
                CAP_DAT_001_ING = component "CAP.DAT.001.ING" "Event Ingestion" "stack-tbd" {
                    tags "not-scaffolded" "tech:stack-tbd" "level:L2"
                }
                CAP_DAT_001_MOD = component "CAP.DAT.001.MOD" "Score Analytics Model" "stack-tbd" {
                    tags "not-scaffolded" "tech:stack-tbd" "level:L2"
                }
                CAP_DAT_001_REP = component "CAP.DAT.001.REP" "Programme Reporting" "stack-tbd" {
                    tags "not-scaffolded" "tech:stack-tbd" "level:L2"
                }
            }
            zone_B2B = container "EXCHANGE_B2B" "EXCHANGE_B2B zone" "group" {
                tags "zone:B2B" "capability-self"
                CAP_B2B_001_CRD = component "CAP.B2B.001.CRD" "Dedicated Card Management" "stack-tbd" {
                    tags "not-scaffolded" "tech:stack-tbd" "level:L2"
                }
                CAP_B2B_001_FLW = component "CAP.B2B.001.FLW" "Financial Flow Management" "stack-tbd" {
                    tags "not-scaffolded" "tech:stack-tbd" "level:L2"
                }
                CAP_B2B_001_OBK = component "CAP.B2B.001.OBK" "Open Banking Integration" "stack-tbd" {
                    tags "not-scaffolded" "tech:stack-tbd" "level:L2"
                }
            }
            zone_REF = container "REFERENTIAL" "REFERENTIAL zone" "group" {
                tags "zone:REF" "capability-self"
                CAP_REF_001_PRE = component "CAP.REF.001.PRE" "Prescriber Referential" "stack-tbd" {
                    tags "not-scaffolded" "tech:stack-tbd" "level:L2"
                }
                CAP_REF_001_TIE = component "CAP.REF.001.TIE" "Tier Referential" "stack-tbd" {
                    tags "not-scaffolded" "tech:stack-tbd" "level:L2"
                }
            }
            zone_STR = container "STEERING" "STEERING zone" "group" {
                tags "zone:STR" "capability-self"
                CAP_STR_001_AUD = component "CAP.STR.001.AUD" "Programme Compliance Audit" "stack-tbd" {
                    tags "not-scaffolded" "tech:stack-tbd" "level:L2"
                }
                CAP_STR_001_GOV = component "CAP.STR.001.GOV" "Programme Governance" "stack-tbd" {
                    tags "not-scaffolded" "tech:stack-tbd" "level:L2"
                }
                CAP_STR_001_KPI = component "CAP.STR.001.KPI" "Performance Monitoring" "stack-tbd" {
                    tags "not-scaffolded" "tech:stack-tbd" "level:L2"
                }
            }
            zone_SUP = container "SUPPORT" "SUPPORT zone" "group" {
                tags "zone:SUP" "capability-self"
                CAP_SUP_001_AUD = component "CAP.SUP.001.AUD" "Audit & Traceability" "stack-tbd" {
                    tags "not-scaffolded" "tech:stack-tbd" "level:L2"
                }
                CAP_SUP_001_CON = component "CAP.SUP.001.CON" "Consent Management" "stack-tbd" {
                    tags "not-scaffolded" "tech:stack-tbd" "level:L2"
                }
                CAP_SUP_001_RET = component "CAP.SUP.001.RET" "Beneficiary Rights" "stack-tbd" {
                    tags "not-scaffolded" "tech:stack-tbd" "level:L2"
                }
                CAP_SUP_002_BEN = component "CAP.SUP.002.BEN" "Beneficiary Identity Anchor" "python" {
                    tags "implemented:mode-a" "tech:python" "level:L2"
                }
            }
        }

        beneficiary -> reliever.zone_CHN "Uses the beneficiary journey" "HTTPS"
        prescriber -> reliever.zone_CHN "Uses the prescriber portal" "HTTPS"
        partner_bank -> reliever.zone_B2B "Card / Open Banking flows" "HTTPS"
        regulator -> reliever.zone_STR "Audits programme governance" "HTTPS"
        reliever.zone_BSP -> reliever.zone_CHN "Resource events" "RabbitMQ" "upstream-event"
        reliever.zone_BSP -> reliever.zone_B2B "Resource events" "RabbitMQ" "upstream-event"
        reliever.zone_BSP -> reliever.zone_SUP "Resource events" "RabbitMQ" "upstream-event"
        reliever.zone_CHN -> reliever.zone_BSP "Resource events" "RabbitMQ" "upstream-event"
        reliever.zone_DAT -> reliever.zone_STR "Resource events" "RabbitMQ" "upstream-event"
        reliever.zone_SUP -> reliever.zone_STR "Resource events" "RabbitMQ" "upstream-event"
    }

    views {
        systemLandscape "Enterprise-Landscape" {
            include *
            autoLayout lr
        }
        systemContext reliever "Reliever-Context" {
            include *
            autoLayout lr
        }
        container reliever "Reliever-Zones" {
            include *
            autoLayout lr
        }
        component reliever.zone_BSP "Zone-BSP-L2s" {
            include *
            autoLayout lr
        }
        component reliever.zone_CHN "Zone-CHN-L2s" {
            include *
            autoLayout lr
        }
        component reliever.zone_DAT "Zone-DAT-L2s" {
            include *
            autoLayout lr
        }
        component reliever.zone_B2B "Zone-B2B-L2s" {
            include *
            autoLayout lr
        }
        component reliever.zone_REF "Zone-REF-L2s" {
            include *
            autoLayout lr
        }
        component reliever.zone_STR "Zone-STR-L2s" {
            include *
            autoLayout lr
        }
        component reliever.zone_SUP "Zone-SUP-L2s" {
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
