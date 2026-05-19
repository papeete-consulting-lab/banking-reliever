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
            zone_BSP = container "Business Service Production" "Business Service Production zone of Reliever." "group" {
                tags "zone:BSP" "capability-self"
                properties {
                    "zone-code" "BUSINESS_SERVICE_PRODUCTION"
                }
                CAP_BSP_001_ARB = component "Prescriber Arbitration" "Handle manual overrides initiated by a prescriber via CHN.002.ACT: apply the human decision, monitor actual outcomes, and return control to the algorithm when reality confirms or refutes the prescriber's decision." "stack-tbd" {
                    tags "not-scaffolded" "tech:stack-tbd" "level:L2"
                    properties {
                        "capability-id" "CAP.BSP.001.ARB"
                    }
                }
                CAP_BSP_001_SCO = component "Behavioural Scoring" "Compute the beneficiary's behavioural score in real time from each transaction and incoming signal. The score is the sole source of truth for tier-change decisions, except for explicitly validated prescriber overrides." "python" {
                    tags "implemented:stub" "tech:python" "level:L2"
                    properties {
                        "capability-id" "CAP.BSP.001.SCO"
                    }
                }
                CAP_BSP_001_SIG = component "Signal Detection" "Detect abnormal behavioural signals surfaced by BSP.004 (notably unconsumed budget envelopes as a relapse signal) and transform them into actionable events for scoring and prescriber coordination." "stack-tbd" {
                    tags "not-scaffolded" "tech:stack-tbd" "level:L2"
                    properties {
                        "capability-id" "CAP.BSP.001.SIG"
                    }
                }
                CAP_BSP_001_TIE = component "Tier Management" "Manage tier transitions (upward progression, demotion) by applying the thresholds defined in CAP.REF.001.TIE. Triggers updates to the dedicated card rules (B2B.001.CRD) on each tier change." "python" {
                    tags "implemented:stub" "tech:python" "level:L2"
                    properties {
                        "capability-id" "CAP.BSP.001.TIE"
                    }
                }
                CAP_BSP_002_CYC = component "Lifecycle Monitoring" "Maintain the beneficiary's current state within the programme: active tier, prescriber statuses, history of key events. Reference point for all other L2 capabilities requiring the beneficiary's current state." "stack-tbd" {
                    tags "not-scaffolded" "tech:stack-tbd" "level:L2"
                    properties {
                        "capability-id" "CAP.BSP.002.CYC"
                    }
                }
                CAP_BSP_002_ELI = component "Eligibility" "Verify that an individual meets the entry criteria for the Reliever programme (demonstrated financial vulnerability, valid prescription) before any enrolment." "stack-tbd" {
                    tags "not-scaffolded" "tech:stack-tbd" "level:L2"
                    properties {
                        "capability-id" "CAP.BSP.002.ELI"
                    }
                }
                CAP_BSP_002_ENR = component "Enrolment" "Formalise the beneficiary's entry into the programme after eligibility verification and GDPR consent. Triggers the creation of the dedicated card (B2B.001.CRD) and the initialisation of open banking access (B2B.001.OBK)." "stack-tbd" {
                    tags "not-scaffolded" "tech:stack-tbd" "level:L2"
                    properties {
                        "capability-id" "CAP.BSP.002.ENR"
                    }
                }
                CAP_BSP_002_EXT = component "Programme Exit" "Manage the beneficiary's exit: successful exit (transfer to standard banking application at the final tier), administrative exit, or voluntary dropout. Triggers card termination (B2B.001.CRD) and rights review (SUP.001.RET)." "stack-tbd" {
                    tags "not-scaffolded" "tech:stack-tbd" "level:L2"
                    properties {
                        "capability-id" "CAP.BSP.002.EXT"
                    }
                }
                CAP_BSP_003_COD = component "Co-Decision" "Formalise decisions requiring agreement from multiple prescribers: collect positions, resolve disagreements, produce a validated collective decision transmitted to BSP.001.TIE for application." "stack-tbd" {
                    tags "not-scaffolded" "tech:stack-tbd" "level:L2"
                    properties {
                        "capability-id" "CAP.BSP.003.COD"
                    }
                }
                CAP_BSP_003_NOT = component "Prescriber Notification & Communication" "Notify the relevant prescribers of significant events in the beneficiary's journey (behavioural alert, tier change, co-decision request) according to their rights and channel preferences." "stack-tbd" {
                    tags "not-scaffolded" "tech:stack-tbd" "level:L2"
                    properties {
                        "capability-id" "CAP.BSP.003.NOT"
                    }
                }
                CAP_BSP_003_ROL = component "Prescriber Role Management" "Define and maintain prescriber roles on each beneficiary case: who can see what, who can act, who co-decides. Visibility is filtered by role to respect distinct professional confidentiality obligations (medical, social, banking)." "stack-tbd" {
                    tags "not-scaffolded" "tech:stack-tbd" "level:L2"
                    properties {
                        "capability-id" "CAP.BSP.003.ROL"
                    }
                }
                CAP_BSP_004_ALT = component "Behavioural Alerts" "Detect and surface abnormal behavioural patterns from the transaction stream to BSP.001.SIG: bypass attempts, recurring declines, systematically unconsumed budgets. These signals feed the scoring without directly modifying operations." "stack-tbd" {
                    tags "not-scaffolded" "tech:stack-tbd" "level:L2"
                    properties {
                        "capability-id" "CAP.BSP.004.ALT"
                    }
                }
                CAP_BSP_004_AUT = component "Transaction Authorisation" "Authorise or decline each transaction on the dedicated card by applying the current tier rules (limits, authorised categories, authorised merchants) in real time. This is the universal and non-bypassable control point of the programme." "stack-tbd" {
                    tags "not-scaffolded" "tech:stack-tbd" "level:L2"
                    properties {
                        "capability-id" "CAP.BSP.004.AUT"
                    }
                }
                CAP_BSP_004_ENV = component "Budget Envelope Management" "Allocate and track budget envelopes by spending category according to the current tier. Triggers card funding (B2B.001.FLW) and produces depletion signals. An unconsumed budget triggers a potential relapse signal." "stack-tbd" {
                    tags "implemented:stub" "tech:stack-tbd" "level:L2"
                    properties {
                        "capability-id" "CAP.BSP.004.ENV"
                    }
                }
            }
            zone_CHN = container "Channel" "Channel zone of Reliever." "group" {
                tags "zone:CHN" "capability-self"
                properties {
                    "zone-code" "CHANNEL"
                }
                CAP_CHN_001_DSH = component "Beneficiary Dashboard" "Expose to the beneficiary a synthetic view of their financial situation adapted to their tier: available balance, envelopes, transaction history. The interface is calibrated to encourage without patronising — dignity is a functional constraint." "dotnet" {
                    tags "implemented:channel-impl" "tech:dotnet" "level:L2"
                    properties {
                        "capability-id" "CAP.CHN.001.DSH"
                    }
                }
                CAP_CHN_001_NOT = component "Beneficiary Notifications" "Notify the beneficiary of relevant events in their journey: declined transaction, tier change, message from a prescriber, budget alert. Tone and content respect the dignity constraint." "stack-tbd" {
                    tags "not-scaffolded" "tech:stack-tbd" "level:L2"
                    properties {
                        "capability-id" "CAP.CHN.001.NOT"
                    }
                }
                CAP_CHN_001_PUR = component "Purchase Assistance" "Provide contextualised assistance at the point of purchase: budget availability check before payment, cheaper alternatives, price comparison. This capability is the UX manifestation of real-time behavioural control." "stack-tbd" {
                    tags "not-scaffolded" "tech:stack-tbd" "level:L2"
                    properties {
                        "capability-id" "CAP.CHN.001.PUR"
                    }
                }
                CAP_CHN_002_ACT = component "Prescriber Actions" "Allow authorised prescribers to take actions on a case: manual tier override, co-decision initiation, envelope rule adjustment. These actions are forwarded to BSP.003.COD or BSP.001.ARB." "stack-tbd" {
                    tags "not-scaffolded" "tech:stack-tbd" "level:L2"
                    properties {
                        "capability-id" "CAP.CHN.002.ACT"
                    }
                }
                CAP_CHN_002_REP = component "Prescriber Reporting" "Provide prescribers with aggregated monitoring reports on the beneficiary: score evolution, tier history, behavioural trends. Data comes from DAT.001.REP and is filtered by the prescriber's rights." "stack-tbd" {
                    tags "not-scaffolded" "tech:stack-tbd" "level:L2"
                    properties {
                        "capability-id" "CAP.CHN.002.REP"
                    }
                }
                CAP_CHN_002_VIE = component "Prescriber Beneficiary View" "Expose to prescribers a filtered view of the beneficiary case according to their role and rights. A doctor does not see the same data as a banker. Access requires Consent.Granted (SUP.001.CON) as a precondition." "stack-tbd" {
                    tags "not-scaffolded" "tech:stack-tbd" "level:L2"
                    properties {
                        "capability-id" "CAP.CHN.002.VIE"
                    }
                }
            }
            zone_DAT = container "Data Analytics" "Data Analytics zone of Reliever." "group" {
                tags "zone:DAT" "capability-self"
                properties {
                    "zone-code" "DATA_ANALYTICS"
                }
                CAP_DAT_001_ING = component "Event Ingestion" "Collect and consolidate in decoupled analytics mode all behavioural events produced by the programme (BSP.001, BSP.002, BSP.003, BSP.004) to feed the analytics pipelines. Strict separation from the operational transactional pipeline." "stack-tbd" {
                    tags "not-scaffolded" "tech:stack-tbd" "level:L2"
                    properties {
                        "capability-id" "CAP.DAT.001.ING"
                    }
                }
                CAP_DAT_001_MOD = component "Score Analytics Model" "Analyse aggregated behavioural patterns, improve the scoring model and propose tier threshold updates. ScoreModel.Updated is sent to STR.001.GOV for validation — never directly to BSP.001.SCO, preventing any uncontrolled feedback loop." "stack-tbd" {
                    tags "not-scaffolded" "tech:stack-tbd" "level:L2"
                    properties {
                        "capability-id" "CAP.DAT.001.MOD"
                    }
                }
                CAP_DAT_001_REP = component "Programme Reporting" "Produce dashboards and monitoring reports on the overall effectiveness of the remediation programme: progression rate, relapse rate, exit rate. This data feeds STR.001.KPI for programme governance decisions." "stack-tbd" {
                    tags "not-scaffolded" "tech:stack-tbd" "level:L2"
                    properties {
                        "capability-id" "CAP.DAT.001.REP"
                    }
                }
            }
            zone_B2B = container "Exchange B2b" "Exchange B2b zone of Reliever." "group" {
                tags "zone:B2B" "capability-self"
                properties {
                    "zone-code" "EXCHANGE_B2B"
                }
                CAP_B2B_001_CRD = component "Dedicated Card Management" "Drive the complete lifecycle of the Reliever dedicated card — issuance, activation, suspension, termination — in liaison with an approved issuing partner. Card usage rules (limits, categories) are synchronised with the current tier." "stack-tbd" {
                    tags "not-scaffolded" "tech:stack-tbd" "level:L2"
                    properties {
                        "capability-id" "CAP.B2B.001.CRD"
                    }
                }
                CAP_B2B_001_FLW = component "Financial Flow Management" "Orchestrate the funding of the dedicated card from the beneficiary's main account, ensure flow reconciliation and handle anomalies. Triggered by envelope events from BSP.004.ENV." "stack-tbd" {
                    tags "not-scaffolded" "tech:stack-tbd" "level:L2"
                    properties {
                        "capability-id" "CAP.B2B.001.FLW"
                    }
                }
                CAP_B2B_001_OBK = component "Open Banking Integration" "Access and refresh the beneficiary's main account financial data via open banking APIs (PSD2). Requires prior Consent.Granted. Makes Reliever independent of inter-bank agreements." "stack-tbd" {
                    tags "not-scaffolded" "tech:stack-tbd" "level:L2"
                    properties {
                        "capability-id" "CAP.B2B.001.OBK"
                    }
                }
            }
            zone_REF = container "Referential" "Referential zone of Reliever." "group" {
                tags "zone:REF" "capability-self"
                properties {
                    "zone-code" "REFERENTIAL"
                }
                CAP_REF_001_PRE = component "Prescriber Referential" "Hold and maintain the canonical identity of prescribers and their organisations. Distinguishes prescriber types (banker, doctor, social worker) and their respective authorisations within the programme." "stack-tbd" {
                    tags "not-scaffolded" "tech:stack-tbd" "level:L2"
                    properties {
                        "capability-id" "CAP.REF.001.PRE"
                    }
                }
                CAP_REF_001_TIE = component "Tier Referential" "Hold and maintain the canonical tier definitions: usage rules, transition thresholds, associated rights. Any modification goes through this L2 and triggers Tier.DefinitionUpdated, consumed in cascade by BSP.001, BSP.004 and B2B.001." "stack-tbd" {
                    tags "not-scaffolded" "tech:stack-tbd" "level:L2"
                    properties {
                        "capability-id" "CAP.REF.001.TIE"
                    }
                }
            }
            zone_STR = container "Steering" "Steering zone of Reliever." "group" {
                tags "zone:STR" "capability-self"
                properties {
                    "zone-code" "STEERING"
                }
                CAP_STR_001_AUD = component "Programme Compliance Audit" "Verify the programme's overall regulatory compliance (banking, medical and social frameworks). Distinct from SUP.001.AUD (technical GDPR audit): STR.001.AUD certifies programme-level regulatory compliance, with the Compliance Officer as the principal actor." "stack-tbd" {
                    tags "not-scaffolded" "tech:stack-tbd" "level:L2"
                    properties {
                        "capability-id" "CAP.STR.001.AUD"
                    }
                }
                CAP_STR_001_GOV = component "Programme Governance" "Define and evolve programme governance policies: eligibility rules, tier thresholds, co-decision protocols. Validates scoring model updates (ScoreModel.Updated from DAT.001.MOD) before any production deployment." "stack-tbd" {
                    tags "not-scaffolded" "tech:stack-tbd" "level:L2"
                    properties {
                        "capability-id" "CAP.STR.001.GOV"
                    }
                }
                CAP_STR_001_KPI = component "Performance Monitoring" "Measure programme effectiveness at scale: progression rate, relapse rate, successful exit rate, perceived dignity. Consumes DAT.001.REP reports and produces ProgrammePerformance.Evaluated for governance decisions." "stack-tbd" {
                    tags "not-scaffolded" "tech:stack-tbd" "level:L2"
                    properties {
                        "capability-id" "CAP.STR.001.KPI"
                    }
                }
            }
            zone_SUP = container "Support" "Support zone of Reliever." "group" {
                tags "zone:SUP" "capability-self"
                properties {
                    "zone-code" "SUPPORT"
                }
                CAP_SUP_001_AUD = component "Audit & Traceability" "Log all accesses and actions on beneficiary data, across all capabilities. Cross-cutting capability: 100% of beneficiary data accesses must produce DataAccess.Logged — a GDPR regulatory obligation." "stack-tbd" {
                    tags "not-scaffolded" "tech:stack-tbd" "level:L2"
                    properties {
                        "capability-id" "CAP.SUP.001.AUD"
                    }
                }
                CAP_SUP_001_CON = component "Consent Management" "Collect, store, manage and honour the beneficiary's GDPR consents for each type of data sharing. Consent.Granted is a blocking precondition for enrolment, open banking, and any prescriber consultation." "stack-tbd" {
                    tags "not-scaffolded" "tech:stack-tbd" "level:L2"
                    properties {
                        "capability-id" "CAP.SUP.001.CON"
                    }
                }
                CAP_SUP_001_RET = component "Beneficiary Rights" "Process the beneficiary's GDPR rights requests (access, rectification, erasure, portability, objection) within the legal timeframe (1 month). Triggered notably by programme exit (BSP.002.EXT)." "stack-tbd" {
                    tags "not-scaffolded" "tech:stack-tbd" "level:L2"
                    properties {
                        "capability-id" "CAP.SUP.001.RET"
                    }
                }
                CAP_SUP_002_BEN = component "Beneficiary Identity Anchor" "Hold the canonical beneficiary identity record, mint its UUIDv7 with a no-recycle-forever guarantee, and operate the GDPR Art. 17 pseudonymisation-at-anchor mechanics. Sole L2 of CAP.SUP.002. Relocated from CAP.REF.001 on 2026-05-15 per ADR-BCM-FUNC-0016 — golden record rule preserved." "python" {
                    tags "implemented:mode-a" "tech:python" "level:L2"
                    properties {
                        "capability-id" "CAP.SUP.002.BEN"
                    }
                }
            }
        }

        beneficiary -> reliever.zone_CHN "Uses the beneficiary journey" "HTTPS"
        prescriber -> reliever.zone_CHN "Uses the prescriber portal" "HTTPS"
        partner_bank -> reliever.zone_B2B "Card / Open Banking flows" "HTTPS"
        regulator -> reliever.zone_STR "Audits programme governance" "HTTPS"
        reliever.zone_BSP -> reliever.zone_CHN "Business events" "Business event subscription" "upstream-event"
        reliever.zone_BSP -> reliever.zone_B2B "Business events" "Business event subscription" "upstream-event"
        reliever.zone_BSP -> reliever.zone_SUP "Business events" "Business event subscription" "upstream-event"
        reliever.zone_CHN -> reliever.zone_BSP "Business events" "Business event subscription" "upstream-event"
        reliever.zone_DAT -> reliever.zone_STR "Business events" "Business event subscription" "upstream-event"
        reliever.zone_SUP -> reliever.zone_STR "Business events" "Business event subscription" "upstream-event"
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
