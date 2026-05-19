workspace "Budget Envelope Management (CAP.BSP.004.ENV)" "Allocate and track budget envelopes by spending category according to the current tier. Triggers card funding (B2B.001.FLW) and produces depletion signals. An unconsumed budget triggers a potential relapse signal." {

    !identifiers hierarchical

    model {
        CAP_BSP_001_TIE = softwareSystem "Tier Management" "Upstream capability (CAP.BSP.001.TIE)." {
            tags "external-capability"
            properties {
                "capability-id" "CAP.BSP.001.TIE"
            }
        }
        CAP_BSP_002_ENR = softwareSystem "Enrolment" "Upstream capability (CAP.BSP.002.ENR)." {
            tags "external-capability"
            properties {
                "capability-id" "CAP.BSP.002.ENR"
            }
        }

        CAP_BSP_004_ENV = softwareSystem "Budget Envelope Management" "Allocate and track budget envelopes by spending category according to the current tier. Triggers card funding (B2B.001.FLW) and produces depletion signals. An unconsumed budget triggers a potential relapse signal." {
            tags "capability-self" "level:L2" "zone:BSP" "domain:supporting"
            properties {
                "capability-id" "CAP.BSP.004.ENV"
                "parent" "CAP.BSP.004"
                "zoning" "BUSINESS_SERVICE_PRODUCTION"
                "owner" "Reliever Programme Directorate"
                "tech-stack" "stack-not-decided"
                "implementation-status" "stub"
                "adr:ADR-BCM-FUNC-0008" "https://github.com/Banking-Reliever/banking-knowledge/blob/main/func-adr/ADR-BCM-FUNC-0008-L2-BSP004-transaction-control.md"
                "adr:ADR-BCM-GOV-0003" "https://github.com/Banking-Reliever/banking-knowledge/blob/main/adr/ADR-BCM-GOV-0003-periodic-stability-review.md"
                "adr:ADR-BCM-GOV-0002" "https://github.com/Banking-Reliever/banking-knowledge/blob/main/adr/ADR-BCM-GOV-0002.md"
                "adr:ADR-BCM-GOV-0001" "https://github.com/Banking-Reliever/banking-knowledge/blob/main/adr/ADR-BCM-GOV-0001.md"
                "adr:ADR-PROD-0005" "https://github.com/Banking-Reliever/banking-knowledge/blob/main/product-vision/adr/ADR-PROD-0005-dignity-as-functional-condition.md"
                "adr:ADR-PROD-0004" "https://github.com/Banking-Reliever/banking-knowledge/blob/main/product-vision/adr/ADR-PROD-0004-tier-algorithm-prescriber-override.md"
                "adr:ADR-PROD-0006" "https://github.com/Banking-Reliever/banking-knowledge/blob/main/product-vision/adr/ADR-PROD-0006-bypass-detection-unconsumed-envelope.md"
                "adr:ADR-PROD-0002" "https://github.com/Banking-Reliever/banking-knowledge/blob/main/product-vision/adr/ADR-PROD-0002-primary-beneficiary-multi-prescriber.md"
                "adr:ADR-PROD-0003" "https://github.com/Banking-Reliever/banking-knowledge/blob/main/product-vision/adr/ADR-PROD-0003-scope-open-banking-protocol.md"
                "adr:ADR-PROD-0001" "https://github.com/Banking-Reliever/banking-knowledge/blob/main/product-vision/adr/ADR-PROD-0001-service-offer-framing.md"
                "adr:ADR-TECH-STRAT-003" "https://github.com/Banking-Reliever/banking-knowledge/blob/main/tech-vision/adr/ADR-TECH-STRAT-003-api-contract-strategy.md"
                "adr:ADR-TECH-STRAT-002" "https://github.com/Banking-Reliever/banking-knowledge/blob/main/tech-vision/adr/ADR-TECH-STRAT-002-microservice-runtime.md"
                "adr:ADR-TECH-STRAT-006" "https://github.com/Banking-Reliever/banking-knowledge/blob/main/tech-vision/adr/ADR-TECH-STRAT-006-hosting-deployment.md"
                "adr:ADR-TECH-STRAT-005" "https://github.com/Banking-Reliever/banking-knowledge/blob/main/tech-vision/adr/ADR-TECH-STRAT-005-observability-governance.md"
                "adr:ADR-TECH-STRAT-007" "https://github.com/Banking-Reliever/banking-knowledge/blob/main/tech-vision/adr/ADR-TECH-STRAT-007-identifier-strategy.md"
                "adr:ADR-TECH-STRAT-001" "https://github.com/Banking-Reliever/banking-knowledge/blob/main/tech-vision/adr/ADR-TECH-STRAT-001-event-infrastructure.md"
                "adr:ADR-TECH-STRAT-008" "https://github.com/Banking-Reliever/banking-knowledge/blob/main/tech-vision/adr/ADR-TECH-STRAT-008-information-publication-model.md"
                "adr:ADR-TECH-STRAT-004" "https://github.com/Banking-Reliever/banking-knowledge/blob/main/tech-vision/adr/ADR-TECH-STRAT-004-data-referential-layer.md"
            }
            stub = container "Contract stub" "Contract stub" "stack-not-decided · Mode B (contract stub)" {
                tags "implemented:stub" "tech:stack-not-decided"
                properties {
                    "loc" "sources/CAP.BSP.004.ENV/stub"
                    "github" "https://github.com/Banking-Reliever/banking/blob/main/sources/CAP.BSP.004.ENV/stub"
                }
                AGG_BSP_004_ENV_PERIOD_BUDGET = component "PERIOD BUDGET" "Aggregate (DDD) — AGG.BSP.004.ENV.PERIOD_BUDGET" {
                    tags "ddd:aggregate"
                    properties { "id" "AGG.BSP.004.ENV.PERIOD_BUDGET" }
                }
                PRJ_BSP_004_ENV_CURRENT_PERIOD_BUDGET_VIEW = component "CURRENT PERIOD BUDGET VIEW" "Read model / CQRS — PRJ.BSP.004.ENV.CURRENT_PERIOD_BUDGET_VIEW" {
                    tags "ddd:read-model"
                    properties { "id" "PRJ.BSP.004.ENV.CURRENT_PERIOD_BUDGET_VIEW" }
                }
                PRJ_BSP_004_ENV_ENVELOPE_HISTORY = component "ENVELOPE HISTORY" "Read model / CQRS — PRJ.BSP.004.ENV.ENVELOPE_HISTORY" {
                    tags "ddd:read-model"
                    properties { "id" "PRJ.BSP.004.ENV.ENVELOPE_HISTORY" }
                }
                QRY_BSP_004_ENV_GET_CURRENT_PERIOD_BUDGET = component "GET CURRENT PERIOD BUDGET" "Read model / CQRS — QRY.BSP.004.ENV.GET_CURRENT_PERIOD_BUDGET" {
                    tags "ddd:read-model"
                    properties { "id" "QRY.BSP.004.ENV.GET_CURRENT_PERIOD_BUDGET" }
                }
                QRY_BSP_004_ENV_GET_ENVELOPE_BY_CATEGORY = component "GET ENVELOPE BY CATEGORY" "Read model / CQRS — QRY.BSP.004.ENV.GET_ENVELOPE_BY_CATEGORY" {
                    tags "ddd:read-model"
                    properties { "id" "QRY.BSP.004.ENV.GET_ENVELOPE_BY_CATEGORY" }
                }
                QRY_BSP_004_ENV_LIST_ENVELOPE_HISTORY = component "LIST ENVELOPE HISTORY" "Read model / CQRS — QRY.BSP.004.ENV.LIST_ENVELOPE_HISTORY" {
                    tags "ddd:read-model"
                    properties { "id" "QRY.BSP.004.ENV.LIST_ENVELOPE_HISTORY" }
                }
                POL_BSP_004_ENV_ON_BENEFICIARY_ENROLLED = component "ON BENEFICIARY ENROLLED" "Policy / reactive saga — POL.BSP.004.ENV.ON_BENEFICIARY_ENROLLED" {
                    tags "ddd:policy"
                    properties { "id" "POL.BSP.004.ENV.ON_BENEFICIARY_ENROLLED" }
                }
                POL_BSP_004_ENV_ON_TIER_UPGRADED = component "ON TIER UPGRADED" "Policy / reactive saga — POL.BSP.004.ENV.ON_TIER_UPGRADED" {
                    tags "ddd:policy"
                    properties { "id" "POL.BSP.004.ENV.ON_TIER_UPGRADED" }
                }
                POL_BSP_004_ENV_ON_TRANSACTION_AUTHORIZED = component "ON TRANSACTION AUTHORIZED" "Policy / reactive saga — POL.BSP.004.ENV.ON_TRANSACTION_AUTHORIZED" {
                    tags "ddd:policy"
                    properties { "id" "POL.BSP.004.ENV.ON_TRANSACTION_AUTHORIZED" }
                }
                POL_BSP_004_ENV_ON_PERIOD_END_DUE = component "ON PERIOD END DUE" "Policy / reactive saga — POL.BSP.004.ENV.ON_PERIOD_END_DUE" {
                    tags "ddd:policy"
                    properties { "id" "POL.BSP.004.ENV.ON_PERIOD_END_DUE" }
                }
                EVT_BSP_004_ENVELOPE_ALLOCATED = component "ENVELOPE ALLOCATED" "Business event publisher — EVT.BSP.004.ENVELOPE_ALLOCATED" {
                    tags "ddd:publisher"
                    properties { "id" "EVT.BSP.004.ENVELOPE_ALLOCATED" }
                }
                EVT_BSP_004_ENVELOPE_CONSUMED = component "ENVELOPE CONSUMED" "Business event publisher — EVT.BSP.004.ENVELOPE_CONSUMED" {
                    tags "ddd:publisher"
                    properties { "id" "EVT.BSP.004.ENVELOPE_CONSUMED" }
                }
                EVT_BSP_004_ENVELOPE_DEPLETED = component "ENVELOPE DEPLETED" "Business event publisher — EVT.BSP.004.ENVELOPE_DEPLETED" {
                    tags "ddd:publisher"
                    properties { "id" "EVT.BSP.004.ENVELOPE_DEPLETED" }
                }
                EVT_BSP_004_ENVELOPE_UNCONSUMED = component "ENVELOPE UNCONSUMED" "Business event publisher — EVT.BSP.004.ENVELOPE_UNCONSUMED" {
                    tags "ddd:publisher"
                    properties { "id" "EVT.BSP.004.ENVELOPE_UNCONSUMED" }
                }
            }
        }

        CAP_BSP_001_TIE -> CAP_BSP_004_ENV.stub "TIER UPGRADED" "Business event subscription" "upstream-event"

        CAP_BSP_002_ENR -> CAP_BSP_004_ENV.stub "BENEFICIARY ENROLLED" "Business event subscription" "upstream-event"

        CAP_BSP_004_ENV_downstream_consumers = softwareSystem "Downstream consumers" "Any capability subscribed to the business events emitted by this one." {
            tags "external-capability"
        }
        CAP_BSP_004_ENV.stub -> CAP_BSP_004_ENV_downstream_consumers "ENVELOPE ALLOCATED, ENVELOPE CONSUMED, ENVELOPE DEPLETED, ENVELOPE UNCONSUMED" "Business event" "downstream-event"
    }

    views {
        systemContext CAP_BSP_004_ENV "L2-Context" {
            include *
            autoLayout lr
        }
        container CAP_BSP_004_ENV "L2-Containers" {
            include *
            autoLayout lr
        }
        component CAP_BSP_004_ENV.stub "L2-Components-stub" {
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
