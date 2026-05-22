workspace "Behavioural Scoring (CAP.BSP.001.SCO)" "Compute the beneficiary's behavioural score in real time from each transaction and incoming signal. The score is the sole source of truth for tier-change decisions, except for explicitly validated prescriber overrides." {

    !identifiers hierarchical

    model {
        CAP_BSP_001_SIG = softwareSystem "Signal Detection" "Upstream capability (CAP.BSP.001.SIG)." {
            tags "external-capability"
            properties {
                "capability-id" "CAP.BSP.001.SIG"
            }
        }
        CAP_BSP_004_AUT = softwareSystem "Transaction Authorisation" "Upstream capability (CAP.BSP.004.AUT)." {
            tags "external-capability"
            properties {
                "capability-id" "CAP.BSP.004.AUT"
            }
        }

        CAP_BSP_001_SCO = softwareSystem "Behavioural Scoring" "Compute the beneficiary's behavioural score in real time from each transaction and incoming signal. The score is the sole source of truth for tier-change decisions, except for explicitly validated prescriber overrides." {
            tags "capability-self" "level:L2" "zone:BSP" "domain:core"
            properties {
                "capability-id" "CAP.BSP.001.SCO"
                "parent" "CAP.BSP.001"
                "zoning" "BUSINESS_SERVICE_PRODUCTION"
                "owner" "Reliever Programme Directorate"
                "tech-stack" "python+fastapi+postgresql+kafka+rabbitmq"
                "implementation-status" "stub"
                "adr:ADR-BCM-FUNC-0005" "https://github.com/Banking-PapeeteConsulting/reliever-knowledge/blob/main/func-adr/ADR-BCM-FUNC-0005-L2-BSP001-behavioural-remediation.md"
                "adr:ADR-TECH-TACT-003" "https://github.com/Banking-PapeeteConsulting/reliever-knowledge/blob/main/tech-adr/ADR-TECH-TACT-003-bsp001-sco-behavioral-scoring.md"
                "adr:ADR-BCM-URBA-0003" "https://github.com/Banking-PapeeteConsulting/reliever-knowledge/blob/main/adr/ADR-BCM-URBA-0003-1-capability-1-responsibility.md"
                "adr:ADR-BCM-URBA-0007" "https://github.com/Banking-PapeeteConsulting/reliever-knowledge/blob/main/adr/ADR-BCM-URBA-0007-normalized-event-meta-model.md"
                "adr:ADR-BCM-URBA-0008" "https://github.com/Banking-PapeeteConsulting/reliever-knowledge/blob/main/adr/ADR-BCM-URBA-0008-event-modeling.md"
                "adr:ADR-BCM-URBA-0009" "https://github.com/Banking-PapeeteConsulting/reliever-knowledge/blob/main/adr/ADR-BCM-URBA-0009-event-capability-definition.md"
                "adr:ADR-BCM-URBA-0010" "https://github.com/Banking-PapeeteConsulting/reliever-knowledge/blob/main/adr/ADR-BCM-URBA-0010-L2-capabilities-as-urbanization-pivot.md"
                "adr:ADR-TECH-STRAT-001" "https://github.com/Banking-PapeeteConsulting/reliever-knowledge/blob/main/tech-vision/adr/ADR-TECH-STRAT-001-event-infrastructure.md"
                "adr:ADR-TECH-STRAT-002" "https://github.com/Banking-PapeeteConsulting/reliever-knowledge/blob/main/tech-vision/adr/ADR-TECH-STRAT-002-microservice-runtime.md"
                "adr:ADR-TECH-STRAT-003" "https://github.com/Banking-PapeeteConsulting/reliever-knowledge/blob/main/tech-vision/adr/ADR-TECH-STRAT-003-api-contract-strategy.md"
                "adr:ADR-TECH-STRAT-004" "https://github.com/Banking-PapeeteConsulting/reliever-knowledge/blob/main/tech-vision/adr/ADR-TECH-STRAT-004-data-referential-layer.md"
                "adr:ADR-TECH-STRAT-005" "https://github.com/Banking-PapeeteConsulting/reliever-knowledge/blob/main/tech-vision/adr/ADR-TECH-STRAT-005-observability-governance.md"
                "adr:ADR-TECH-STRAT-006" "https://github.com/Banking-PapeeteConsulting/reliever-knowledge/blob/main/tech-vision/adr/ADR-TECH-STRAT-006-hosting-deployment.md"
                "adr:ADR-TECH-STRAT-007" "https://github.com/Banking-PapeeteConsulting/reliever-knowledge/blob/main/tech-vision/adr/ADR-TECH-STRAT-007-identifier-strategy.md"
                "adr:ADR-TECH-STRAT-008" "https://github.com/Banking-PapeeteConsulting/reliever-knowledge/blob/main/tech-vision/adr/ADR-TECH-STRAT-008-information-publication-model.md"
                "adr:ADR-BCM-GOV-0003" "https://github.com/Banking-PapeeteConsulting/reliever-knowledge/blob/main/adr/ADR-BCM-GOV-0003-periodic-stability-review.md"
                "adr:ADR-BCM-GOV-0002" "https://github.com/Banking-PapeeteConsulting/reliever-knowledge/blob/main/adr/ADR-BCM-GOV-0002.md"
                "adr:ADR-BCM-GOV-0001" "https://github.com/Banking-PapeeteConsulting/reliever-knowledge/blob/main/adr/ADR-BCM-GOV-0001.md"
                "adr:ADR-PROD-0005" "https://github.com/Banking-PapeeteConsulting/reliever-knowledge/blob/main/product-vision/adr/ADR-PROD-0005-dignity-as-functional-condition.md"
                "adr:ADR-PROD-0004" "https://github.com/Banking-PapeeteConsulting/reliever-knowledge/blob/main/product-vision/adr/ADR-PROD-0004-tier-algorithm-prescriber-override.md"
                "adr:ADR-PROD-0006" "https://github.com/Banking-PapeeteConsulting/reliever-knowledge/blob/main/product-vision/adr/ADR-PROD-0006-bypass-detection-unconsumed-envelope.md"
                "adr:ADR-PROD-0002" "https://github.com/Banking-PapeeteConsulting/reliever-knowledge/blob/main/product-vision/adr/ADR-PROD-0002-primary-beneficiary-multi-prescriber.md"
                "adr:ADR-PROD-0003" "https://github.com/Banking-PapeeteConsulting/reliever-knowledge/blob/main/product-vision/adr/ADR-PROD-0003-scope-open-banking-protocol.md"
                "adr:ADR-PROD-0001" "https://github.com/Banking-PapeeteConsulting/reliever-knowledge/blob/main/product-vision/adr/ADR-PROD-0001-service-offer-framing.md"
            }
            stub = container "Contract stub" "Contract stub" "python+fastapi+postgresql+kafka+rabbitmq · Mode B (contract stub)" {
                tags "implemented:stub" "tech:python+fastapi+postgresql+kafka+rabbitmq"
                properties {
                    "loc" "sources/CAP.BSP.001.SCO/stub"
                    "github" "https://github.com/Banking-PapeeteConsulting/banking-reliever/blob/main/sources/CAP.BSP.001.SCO/stub"
                }
                AGG_BSP_001_SCO_SCORE_OF_BENEFICIARY = component "SCORE OF BENEFICIARY" "Aggregate (DDD) — AGG.BSP.001.SCO.SCORE_OF_BENEFICIARY" {
                    tags "ddd:aggregate"
                    properties { "id" "AGG.BSP.001.SCO.SCORE_OF_BENEFICIARY" }
                }
                PRJ_BSP_001_SCO_CURRENT_SCORE_VIEW = component "CURRENT SCORE VIEW" "Read model / CQRS — PRJ.BSP.001.SCO.CURRENT_SCORE_VIEW" {
                    tags "ddd:read-model"
                    properties { "id" "PRJ.BSP.001.SCO.CURRENT_SCORE_VIEW" }
                }
                PRJ_BSP_001_SCO_SCORE_HISTORY = component "SCORE HISTORY" "Read model / CQRS — PRJ.BSP.001.SCO.SCORE_HISTORY" {
                    tags "ddd:read-model"
                    properties { "id" "PRJ.BSP.001.SCO.SCORE_HISTORY" }
                }
                QRY_BSP_001_SCO_GET_CURRENT_SCORE = component "GET CURRENT SCORE" "Read model / CQRS — QRY.BSP.001.SCO.GET_CURRENT_SCORE" {
                    tags "ddd:read-model"
                    properties { "id" "QRY.BSP.001.SCO.GET_CURRENT_SCORE" }
                }
                QRY_BSP_001_SCO_LIST_SCORE_HISTORY = component "LIST SCORE HISTORY" "Read model / CQRS — QRY.BSP.001.SCO.LIST_SCORE_HISTORY" {
                    tags "ddd:read-model"
                    properties { "id" "QRY.BSP.001.SCO.LIST_SCORE_HISTORY" }
                }
                POL_BSP_001_SCO_ON_BEHAVIOURAL_TRIGGER = component "ON BEHAVIOURAL TRIGGER" "Policy / reactive saga — POL.BSP.001.SCO.ON_BEHAVIOURAL_TRIGGER" {
                    tags "ddd:policy"
                    properties { "id" "POL.BSP.001.SCO.ON_BEHAVIOURAL_TRIGGER" }
                }
                POL_BSP_001_SCO_ON_ENROLMENT_COMPLETED = component "ON ENROLMENT COMPLETED" "Policy / reactive saga — POL.BSP.001.SCO.ON_ENROLMENT_COMPLETED" {
                    tags "ddd:policy"
                    properties { "id" "POL.BSP.001.SCO.ON_ENROLMENT_COMPLETED" }
                }
                EVT_BSP_001_SCORE_RECOMPUTED = component "SCORE RECOMPUTED" "Business event publisher — EVT.BSP.001.SCORE_RECOMPUTED" {
                    tags "ddd:publisher"
                    properties { "id" "EVT.BSP.001.SCORE_RECOMPUTED" }
                }
                EVT_BSP_001_SCORE_THRESHOLD_REACHED = component "SCORE THRESHOLD REACHED" "Business event publisher — EVT.BSP.001.SCORE_THRESHOLD_REACHED" {
                    tags "ddd:publisher"
                    properties { "id" "EVT.BSP.001.SCORE_THRESHOLD_REACHED" }
                }
            }
        }

        CAP_BSP_001_SIG -> CAP_BSP_001_SCO.stub "PROGRESSION SIGNAL DETECTED, RELAPSE SIGNAL DETECTED" "Business event subscription" "upstream-event"

        CAP_BSP_004_AUT -> CAP_BSP_001_SCO.stub "TRANSACTION AUTHORIZED, TRANSACTION REFUSED" "Business event subscription" "upstream-event"

        CAP_BSP_001_SCO_downstream_consumers = softwareSystem "Downstream consumers" "Any capability subscribed to the business events emitted by this one." {
            tags "external-capability"
        }
        CAP_BSP_001_SCO.stub -> CAP_BSP_001_SCO_downstream_consumers "SCORE RECOMPUTED, SCORE THRESHOLD REACHED" "Business event" "downstream-event"
    }

    views {
        systemContext CAP_BSP_001_SCO "L2-Context" {
            include *
            autoLayout lr
        }
        container CAP_BSP_001_SCO "L2-Containers" {
            include *
            autoLayout lr
        }
        component CAP_BSP_001_SCO.stub "L2-Components-stub" {
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
