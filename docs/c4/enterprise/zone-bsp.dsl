workspace "Zone — Business Service Production" "C4 container view of the Business Service Production zone — each L2 capability is a container." {

    !identifiers hierarchical

    model {
        zone_BSP = softwareSystem "Business Service Production" "Business Service Production zone of the Reliever business capability model." {
            tags "capability-self" "zone:BSP"
            properties {
                "zone-code" "BUSINESS_SERVICE_PRODUCTION"
            }
            CAP_BSP_001_ARB = container "Prescriber Arbitration" "Handle manual overrides initiated by a prescriber via CHN.002.ACT: apply the human decision, monitor actual outcomes, and return control to the algorithm when reality confirms or refutes the prescriber's decision." "stack-tbd" {
                tags "not-scaffolded" "tech:stack-tbd" "parent:CAP.BSP.001"
                properties {
                    "capability-id" "CAP.BSP.001.ARB"
                    "detail-view" "../CAP.BSP.001.ARB/workspace.dsl"
                    "parent" "CAP.BSP.001"
                }
            }
            CAP_BSP_001_SCO = container "Behavioural Scoring" "Compute the beneficiary's behavioural score in real time from each transaction and incoming signal. The score is the sole source of truth for tier-change decisions, except for explicitly validated prescriber overrides." "python" {
                tags "implemented:stub" "tech:python" "parent:CAP.BSP.001"
                properties {
                    "capability-id" "CAP.BSP.001.SCO"
                    "detail-view" "../CAP.BSP.001.SCO/workspace.dsl"
                    "parent" "CAP.BSP.001"
                }
            }
            CAP_BSP_001_SIG = container "Signal Detection" "Detect abnormal behavioural signals surfaced by BSP.004 (notably unconsumed budget envelopes as a relapse signal) and transform them into actionable events for scoring and prescriber coordination." "stack-tbd" {
                tags "not-scaffolded" "tech:stack-tbd" "parent:CAP.BSP.001"
                properties {
                    "capability-id" "CAP.BSP.001.SIG"
                    "detail-view" "../CAP.BSP.001.SIG/workspace.dsl"
                    "parent" "CAP.BSP.001"
                }
            }
            CAP_BSP_001_TIE = container "Tier Management" "Manage tier transitions (upward progression, demotion) by applying the thresholds defined in CAP.REF.001.TIE. Triggers updates to the dedicated card rules (B2B.001.CRD) on each tier change." "python" {
                tags "implemented:stub" "tech:python" "parent:CAP.BSP.001"
                properties {
                    "capability-id" "CAP.BSP.001.TIE"
                    "detail-view" "../CAP.BSP.001.TIE/workspace.dsl"
                    "parent" "CAP.BSP.001"
                }
            }
            CAP_BSP_002_CYC = container "Lifecycle Monitoring" "Maintain the beneficiary's current state within the programme: active tier, prescriber statuses, history of key events. Reference point for all other L2 capabilities requiring the beneficiary's current state." "stack-tbd" {
                tags "not-scaffolded" "tech:stack-tbd" "parent:CAP.BSP.002"
                properties {
                    "capability-id" "CAP.BSP.002.CYC"
                    "detail-view" "../CAP.BSP.002.CYC/workspace.dsl"
                    "parent" "CAP.BSP.002"
                }
            }
            CAP_BSP_002_ELI = container "Eligibility" "Verify that an individual meets the entry criteria for the Reliever programme (demonstrated financial vulnerability, valid prescription) before any enrolment." "stack-tbd" {
                tags "not-scaffolded" "tech:stack-tbd" "parent:CAP.BSP.002"
                properties {
                    "capability-id" "CAP.BSP.002.ELI"
                    "detail-view" "../CAP.BSP.002.ELI/workspace.dsl"
                    "parent" "CAP.BSP.002"
                }
            }
            CAP_BSP_002_ENR = container "Enrolment" "Formalise the beneficiary's entry into the programme after eligibility verification and GDPR consent. Triggers the creation of the dedicated card (B2B.001.CRD) and the initialisation of open banking access (B2B.001.OBK)." "stack-tbd" {
                tags "not-scaffolded" "tech:stack-tbd" "parent:CAP.BSP.002"
                properties {
                    "capability-id" "CAP.BSP.002.ENR"
                    "detail-view" "../CAP.BSP.002.ENR/workspace.dsl"
                    "parent" "CAP.BSP.002"
                }
            }
            CAP_BSP_002_EXT = container "Programme Exit" "Manage the beneficiary's exit: successful exit (transfer to standard banking application at the final tier), administrative exit, or voluntary dropout. Triggers card termination (B2B.001.CRD) and rights review (SUP.001.RET)." "stack-tbd" {
                tags "not-scaffolded" "tech:stack-tbd" "parent:CAP.BSP.002"
                properties {
                    "capability-id" "CAP.BSP.002.EXT"
                    "detail-view" "../CAP.BSP.002.EXT/workspace.dsl"
                    "parent" "CAP.BSP.002"
                }
            }
            CAP_BSP_003_COD = container "Co-Decision" "Formalise decisions requiring agreement from multiple prescribers: collect positions, resolve disagreements, produce a validated collective decision transmitted to BSP.001.TIE for application." "stack-tbd" {
                tags "not-scaffolded" "tech:stack-tbd" "parent:CAP.BSP.003"
                properties {
                    "capability-id" "CAP.BSP.003.COD"
                    "detail-view" "../CAP.BSP.003.COD/workspace.dsl"
                    "parent" "CAP.BSP.003"
                }
            }
            CAP_BSP_003_NOT = container "Prescriber Notification & Communication" "Notify the relevant prescribers of significant events in the beneficiary's journey (behavioural alert, tier change, co-decision request) according to their rights and channel preferences." "stack-tbd" {
                tags "not-scaffolded" "tech:stack-tbd" "parent:CAP.BSP.003"
                properties {
                    "capability-id" "CAP.BSP.003.NOT"
                    "detail-view" "../CAP.BSP.003.NOT/workspace.dsl"
                    "parent" "CAP.BSP.003"
                }
            }
            CAP_BSP_003_ROL = container "Prescriber Role Management" "Define and maintain prescriber roles on each beneficiary case: who can see what, who can act, who co-decides. Visibility is filtered by role to respect distinct professional confidentiality obligations (medical, social, banking)." "stack-tbd" {
                tags "not-scaffolded" "tech:stack-tbd" "parent:CAP.BSP.003"
                properties {
                    "capability-id" "CAP.BSP.003.ROL"
                    "detail-view" "../CAP.BSP.003.ROL/workspace.dsl"
                    "parent" "CAP.BSP.003"
                }
            }
            CAP_BSP_004_ALT = container "Behavioural Alerts" "Detect and surface abnormal behavioural patterns from the transaction stream to BSP.001.SIG: bypass attempts, recurring declines, systematically unconsumed budgets. These signals feed the scoring without directly modifying operations." "stack-tbd" {
                tags "not-scaffolded" "tech:stack-tbd" "parent:CAP.BSP.004"
                properties {
                    "capability-id" "CAP.BSP.004.ALT"
                    "detail-view" "../CAP.BSP.004.ALT/workspace.dsl"
                    "parent" "CAP.BSP.004"
                }
            }
            CAP_BSP_004_AUT = container "Transaction Authorisation" "Authorise or decline each transaction on the dedicated card by applying the current tier rules (limits, authorised categories, authorised merchants) in real time. This is the universal and non-bypassable control point of the programme." "stack-tbd" {
                tags "not-scaffolded" "tech:stack-tbd" "parent:CAP.BSP.004"
                properties {
                    "capability-id" "CAP.BSP.004.AUT"
                    "detail-view" "../CAP.BSP.004.AUT/workspace.dsl"
                    "parent" "CAP.BSP.004"
                }
            }
            CAP_BSP_004_ENV = container "Budget Envelope Management" "Allocate and track budget envelopes by spending category according to the current tier. Triggers card funding (B2B.001.FLW) and produces depletion signals. An unconsumed budget triggers a potential relapse signal." "stack-tbd" {
                tags "implemented:stub" "tech:stack-tbd" "parent:CAP.BSP.004"
                properties {
                    "capability-id" "CAP.BSP.004.ENV"
                    "detail-view" "../CAP.BSP.004.ENV/workspace.dsl"
                    "parent" "CAP.BSP.004"
                }
            }
        }

        CAP_CHN_002_ACT = softwareSystem "Prescriber Actions" "External capability (CAP.CHN.002.ACT) — emits business events consumed by this zone." {
            tags "external-capability"
            properties {
                "capability-id" "CAP.CHN.002.ACT"
            }
        }
        zone_BSP.CAP_BSP_001_TIE -> zone_BSP.CAP_BSP_001_ARB "TIER OVERRIDE APPLIED" "Business event subscription" "upstream-event"
        zone_BSP.CAP_BSP_001_SCO -> zone_BSP.CAP_BSP_001_ARB "SCORE RECOMPUTED" "Business event subscription" "upstream-event"
        zone_BSP.CAP_BSP_004_AUT -> zone_BSP.CAP_BSP_001_SCO "TRANSACTION AUTHORIZED, TRANSACTION REFUSED" "Business event subscription" "upstream-event"
        zone_BSP.CAP_BSP_001_SIG -> zone_BSP.CAP_BSP_001_SCO "PROGRESSION SIGNAL DETECTED, RELAPSE SIGNAL DETECTED" "Business event subscription" "upstream-event"
        zone_BSP.CAP_BSP_004_ENV -> zone_BSP.CAP_BSP_001_SIG "ENVELOPE UNCONSUMED" "Business event subscription" "upstream-event"
        zone_BSP.CAP_BSP_004_AUT -> zone_BSP.CAP_BSP_001_SIG "TRANSACTION AUTHORIZED" "Business event subscription" "upstream-event"
        zone_BSP.CAP_BSP_001_SCO -> zone_BSP.CAP_BSP_001_TIE "SCORE THRESHOLD REACHED" "Business event subscription" "upstream-event"
        zone_BSP.CAP_BSP_003_COD -> zone_BSP.CAP_BSP_001_TIE "OVERRIDE REQUESTED" "Business event subscription" "upstream-event"
        zone_BSP.CAP_BSP_002_ENR -> zone_BSP.CAP_BSP_002_CYC "BENEFICIARY ENROLLED" "Business event subscription" "upstream-event"
        zone_BSP.CAP_BSP_001_SIG -> zone_BSP.CAP_BSP_002_CYC "RELAPSE SIGNAL DETECTED" "Business event subscription" "upstream-event"
        zone_BSP.CAP_BSP_003_COD -> zone_BSP.CAP_BSP_002_ELI "OVERRIDE REQUESTED" "Business event subscription" "upstream-event"
        zone_BSP.CAP_BSP_002_ELI -> zone_BSP.CAP_BSP_002_ENR "ELIGIBILITY VALIDATED" "Business event subscription" "upstream-event"
        zone_BSP.CAP_BSP_001_TIE -> zone_BSP.CAP_BSP_002_EXT "TIER UPGRADED" "Business event subscription" "upstream-event"
        CAP_CHN_002_ACT -> zone_BSP.CAP_BSP_003_COD "OVERRIDE UX TRIGGERED" "Business event subscription" "upstream-event"
        zone_BSP.CAP_BSP_001_SIG -> zone_BSP.CAP_BSP_003_NOT "RELAPSE SIGNAL DETECTED" "Business event subscription" "upstream-event"
        zone_BSP.CAP_BSP_001_TIE -> zone_BSP.CAP_BSP_003_NOT "TIER DOWNGRADED, TIER UPGRADED" "Business event subscription" "upstream-event"
        zone_BSP.CAP_BSP_004_ENV -> zone_BSP.CAP_BSP_003_NOT "ENVELOPE UNCONSUMED" "Business event subscription" "upstream-event"
        zone_BSP.CAP_BSP_002_ENR -> zone_BSP.CAP_BSP_003_ROL "BENEFICIARY ENROLLED" "Business event subscription" "upstream-event"
        zone_BSP.CAP_BSP_004_AUT -> zone_BSP.CAP_BSP_004_ALT "TRANSACTION REFUSED" "Business event subscription" "upstream-event"
        zone_BSP.CAP_BSP_001_TIE -> zone_BSP.CAP_BSP_004_AUT "TIER DOWNGRADED, TIER OVERRIDE APPLIED, TIER UPGRADED" "Business event subscription" "upstream-event"
        zone_BSP.CAP_BSP_002_ENR -> zone_BSP.CAP_BSP_004_ENV "BENEFICIARY ENROLLED" "Business event subscription" "upstream-event"
        zone_BSP.CAP_BSP_001_TIE -> zone_BSP.CAP_BSP_004_ENV "TIER UPGRADED" "Business event subscription" "upstream-event"
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
