workspace "Tier Management (CAP.BSP.001.TIE)" "Manage tier transitions (upward progression, demotion) by applying the thresholds defined in CAP.REF.001.TIE. Triggers updates to the dedicated card rules (B2B.001.CRD) on each tier change." {

    !identifiers hierarchical

    model {
        CAP_BSP_001_SCO = softwareSystem "Behavioural Scoring" "Upstream capability (CAP.BSP.001.SCO)." {
            tags "external-capability"
            properties {
                "capability-id" "CAP.BSP.001.SCO"
            }
        }
        CAP_BSP_003_COD = softwareSystem "Co-Decision" "Upstream capability (CAP.BSP.003.COD)." {
            tags "external-capability"
            properties {
                "capability-id" "CAP.BSP.003.COD"
            }
        }

        CAP_BSP_001_TIE = softwareSystem "Tier Management" "Manage tier transitions (upward progression, demotion) by applying the thresholds defined in CAP.REF.001.TIE. Triggers updates to the dedicated card rules (B2B.001.CRD) on each tier change." {
            tags "capability-self" "level:L2" "zone:BSP" "domain:core"
            properties {
                "capability-id" "CAP.BSP.001.TIE"
                "parent" "CAP.BSP.001"
                "zoning" "BUSINESS_SERVICE_PRODUCTION"
                "owner" "Reliever Programme Directorate"
                "tech-stack" "python+fastapi+postgresql+kafka+rabbitmq"
                "implementation-status" "stub"
                "adr:ADR-BCM-FUNC-0005" "https://github.com/Banking-Reliever/banking-knowledge/blob/main/func-adr/ADR-BCM-FUNC-0005-L2-BSP001-behavioural-remediation.md"
                "adr:ADR-TECH-TACT-004" "https://github.com/Banking-Reliever/banking-knowledge/blob/main/tech-adr/ADR-TECH-TACT-004-bsp001-tie-tier-management.md"
                "adr:ADR-BCM-URBA-0003" "https://github.com/Banking-Reliever/banking-knowledge/blob/main/adr/ADR-BCM-URBA-0003-1-capability-1-responsibility.md"
                "adr:ADR-BCM-URBA-0009" "https://github.com/Banking-Reliever/banking-knowledge/blob/main/adr/ADR-BCM-URBA-0009-event-capability-definition.md"
                "adr:ADR-BCM-URBA-0010" "https://github.com/Banking-Reliever/banking-knowledge/blob/main/adr/ADR-BCM-URBA-0010-L2-capabilities-as-urbanization-pivot.md"
                "adr:ADR-BCM-URBA-0012" "https://github.com/Banking-Reliever/banking-knowledge/blob/main/adr/ADR-BCM-URBA-0012-introduction-of-canonical-business-concept.md"
                "adr:ADR-TECH-STRAT-001" "https://github.com/Banking-Reliever/banking-knowledge/blob/main/tech-vision/adr/ADR-TECH-STRAT-001-event-infrastructure.md"
                "adr:ADR-TECH-STRAT-002" "https://github.com/Banking-Reliever/banking-knowledge/blob/main/tech-vision/adr/ADR-TECH-STRAT-002-microservice-runtime.md"
                "adr:ADR-TECH-STRAT-003" "https://github.com/Banking-Reliever/banking-knowledge/blob/main/tech-vision/adr/ADR-TECH-STRAT-003-api-contract-strategy.md"
                "adr:ADR-TECH-STRAT-004" "https://github.com/Banking-Reliever/banking-knowledge/blob/main/tech-vision/adr/ADR-TECH-STRAT-004-data-referential-layer.md"
                "adr:ADR-TECH-STRAT-005" "https://github.com/Banking-Reliever/banking-knowledge/blob/main/tech-vision/adr/ADR-TECH-STRAT-005-observability-governance.md"
                "adr:ADR-TECH-STRAT-006" "https://github.com/Banking-Reliever/banking-knowledge/blob/main/tech-vision/adr/ADR-TECH-STRAT-006-hosting-deployment.md"
                "adr:ADR-TECH-STRAT-007" "https://github.com/Banking-Reliever/banking-knowledge/blob/main/tech-vision/adr/ADR-TECH-STRAT-007-identifier-strategy.md"
                "adr:ADR-TECH-STRAT-008" "https://github.com/Banking-Reliever/banking-knowledge/blob/main/tech-vision/adr/ADR-TECH-STRAT-008-information-publication-model.md"
                "adr:ADR-BCM-GOV-0003" "https://github.com/Banking-Reliever/banking-knowledge/blob/main/adr/ADR-BCM-GOV-0003-periodic-stability-review.md"
                "adr:ADR-BCM-GOV-0002" "https://github.com/Banking-Reliever/banking-knowledge/blob/main/adr/ADR-BCM-GOV-0002.md"
                "adr:ADR-BCM-GOV-0001" "https://github.com/Banking-Reliever/banking-knowledge/blob/main/adr/ADR-BCM-GOV-0001.md"
                "adr:ADR-PROD-0005" "https://github.com/Banking-Reliever/banking-knowledge/blob/main/product-vision/adr/ADR-PROD-0005-dignity-as-functional-condition.md"
                "adr:ADR-PROD-0004" "https://github.com/Banking-Reliever/banking-knowledge/blob/main/product-vision/adr/ADR-PROD-0004-tier-algorithm-prescriber-override.md"
                "adr:ADR-PROD-0006" "https://github.com/Banking-Reliever/banking-knowledge/blob/main/product-vision/adr/ADR-PROD-0006-bypass-detection-unconsumed-envelope.md"
                "adr:ADR-PROD-0002" "https://github.com/Banking-Reliever/banking-knowledge/blob/main/product-vision/adr/ADR-PROD-0002-primary-beneficiary-multi-prescriber.md"
                "adr:ADR-PROD-0003" "https://github.com/Banking-Reliever/banking-knowledge/blob/main/product-vision/adr/ADR-PROD-0003-scope-open-banking-protocol.md"
                "adr:ADR-PROD-0001" "https://github.com/Banking-Reliever/banking-knowledge/blob/main/product-vision/adr/ADR-PROD-0001-service-offer-framing.md"
            }
            stub = container "Contract stub" "Contract stub" "python+fastapi+postgresql+kafka+rabbitmq · Mode B (contract stub)" {
                tags "implemented:stub" "tech:python+fastapi+postgresql+kafka+rabbitmq"
                properties {
                    "loc" "sources/CAP.BSP.001.TIE/stub"
                    "github" "https://github.com/Banking-Reliever/banking/blob/main/sources/CAP.BSP.001.TIE/stub"
                }
                AGG_BSP_001_TIE_TIER_OF_CASE = component "TIER OF CASE" "Aggregate (DDD) — AGG.BSP.001.TIE.TIER_OF_CASE" {
                    tags "ddd:aggregate"
                    properties { "id" "AGG.BSP.001.TIE.TIER_OF_CASE" }
                }
                PRJ_BSP_001_TIE_CURRENT_TIER_VIEW = component "CURRENT TIER VIEW" "Read model / CQRS — PRJ.BSP.001.TIE.CURRENT_TIER_VIEW" {
                    tags "ddd:read-model"
                    properties { "id" "PRJ.BSP.001.TIE.CURRENT_TIER_VIEW" }
                }
                PRJ_BSP_001_TIE_TIER_HISTORY = component "TIER HISTORY" "Read model / CQRS — PRJ.BSP.001.TIE.TIER_HISTORY" {
                    tags "ddd:read-model"
                    properties { "id" "PRJ.BSP.001.TIE.TIER_HISTORY" }
                }
                QRY_BSP_001_TIE_GET_CURRENT_TIER = component "GET CURRENT TIER" "Read model / CQRS — QRY.BSP.001.TIE.GET_CURRENT_TIER" {
                    tags "ddd:read-model"
                    properties { "id" "QRY.BSP.001.TIE.GET_CURRENT_TIER" }
                }
                QRY_BSP_001_TIE_LIST_TIER_HISTORY = component "LIST TIER HISTORY" "Read model / CQRS — QRY.BSP.001.TIE.LIST_TIER_HISTORY" {
                    tags "ddd:read-model"
                    properties { "id" "QRY.BSP.001.TIE.LIST_TIER_HISTORY" }
                }
                POL_BSP_001_TIE_ON_SCORE_THRESHOLD_REACHED = component "ON SCORE THRESHOLD REACHED" "Policy / reactive saga — POL.BSP.001.TIE.ON_SCORE_THRESHOLD_REACHED" {
                    tags "ddd:policy"
                    properties { "id" "POL.BSP.001.TIE.ON_SCORE_THRESHOLD_REACHED" }
                }
                POL_BSP_001_TIE_ON_ARBITRATION_OVERRIDE_VALIDATED = component "ON ARBITRATION OVERRIDE VALIDATED" "Policy / reactive saga — POL.BSP.001.TIE.ON_ARBITRATION_OVERRIDE_VALIDATED" {
                    tags "ddd:policy"
                    properties { "id" "POL.BSP.001.TIE.ON_ARBITRATION_OVERRIDE_VALIDATED" }
                }
                POL_BSP_001_TIE_ON_ARBITRATION_ALGORITHM_REAFFIRMED = component "ON ARBITRATION ALGORITHM REAFFIRMED" "Policy / reactive saga — POL.BSP.001.TIE.ON_ARBITRATION_ALGORITHM_REAFFIRMED" {
                    tags "ddd:policy"
                    properties { "id" "POL.BSP.001.TIE.ON_ARBITRATION_ALGORITHM_REAFFIRMED" }
                }
                POL_BSP_001_TIE_ON_BENEFICIARY_ENROLLED = component "ON BENEFICIARY ENROLLED" "Policy / reactive saga — POL.BSP.001.TIE.ON_BENEFICIARY_ENROLLED" {
                    tags "ddd:policy"
                    properties { "id" "POL.BSP.001.TIE.ON_BENEFICIARY_ENROLLED" }
                }
                POL_BSP_001_TIE_ON_TIER_DEFINITION_UPDATED = component "ON TIER DEFINITION UPDATED" "Policy / reactive saga — POL.BSP.001.TIE.ON_TIER_DEFINITION_UPDATED" {
                    tags "ddd:policy"
                    properties { "id" "POL.BSP.001.TIE.ON_TIER_DEFINITION_UPDATED" }
                }
                EVT_BSP_001_TIER_UPGRADED = component "TIER UPGRADED" "Business event publisher — EVT.BSP.001.TIER_UPGRADED" {
                    tags "ddd:publisher"
                    properties { "id" "EVT.BSP.001.TIER_UPGRADED" }
                }
                EVT_BSP_001_TIER_DOWNGRADED = component "TIER DOWNGRADED" "Business event publisher — EVT.BSP.001.TIER_DOWNGRADED" {
                    tags "ddd:publisher"
                    properties { "id" "EVT.BSP.001.TIER_DOWNGRADED" }
                }
                EVT_BSP_001_TIER_OVERRIDE_APPLIED = component "TIER OVERRIDE APPLIED" "Business event publisher — EVT.BSP.001.TIER_OVERRIDE_APPLIED" {
                    tags "ddd:publisher"
                    properties { "id" "EVT.BSP.001.TIER_OVERRIDE_APPLIED" }
                }
            }
        }

        CAP_BSP_001_SCO -> CAP_BSP_001_TIE.stub "SCORE THRESHOLD REACHED" "Business event subscription" "upstream-event"

        CAP_BSP_003_COD -> CAP_BSP_001_TIE.stub "OVERRIDE REQUESTED" "Business event subscription" "upstream-event"

        CAP_BSP_001_TIE_downstream_consumers = softwareSystem "Downstream consumers" "Any capability subscribed to the business events emitted by this one." {
            tags "external-capability"
        }
        CAP_BSP_001_TIE.stub -> CAP_BSP_001_TIE_downstream_consumers "TIER DOWNGRADED, TIER OVERRIDE APPLIED, TIER UPGRADED" "Business event" "downstream-event"
    }

    views {
        systemContext CAP_BSP_001_TIE "L2-Context" {
            include *
            autoLayout lr
        }
        container CAP_BSP_001_TIE "L2-Containers" {
            include *
            autoLayout lr
        }
        component CAP_BSP_001_TIE.stub "L2-Components-stub" {
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
