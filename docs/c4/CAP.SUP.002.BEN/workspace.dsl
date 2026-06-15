workspace "Beneficiary Identity Anchor (CAP.SUP.002.BEN)" "Hold the canonical beneficiary identity record, mint its UUIDv7 with a no-recycle-forever guarantee, and operate the GDPR Art. 17 pseudonymisation-at-anchor mechanics. Sole L2 of CAP.SUP.002. Relocated from CAP.REF.001 on 2026-05-15 per ADR-BCM-FUNC-0016 — golden record rule preserved." {

    !identifiers hierarchical

    model {

        CAP_SUP_002_BEN = softwareSystem "Beneficiary Identity Anchor" "Hold the canonical beneficiary identity record, mint its UUIDv7 with a no-recycle-forever guarantee, and operate the GDPR Art. 17 pseudonymisation-at-anchor mechanics. Sole L2 of CAP.SUP.002. Relocated from CAP.REF.001 on 2026-05-15 per ADR-BCM-FUNC-0016 — golden record rule preserved." {
            tags "capability-self" "level:L2" "zone:SUP" "domain:supporting"
            properties {
                "capability-id" "CAP.SUP.002.BEN"
                "parent" "CAP.SUP.002"
                "zoning" "SUPPORT"
                "owner" "IT Security / Identity & DPO (joint custody)"
                "tech-stack" "python+fastapi+postgresql"
                "implementation-status" "mode-a"
                "adr:ADR-BCM-FUNC-0016" "https://github.com/Banking-PapeeteConsulting/reliever-knowledge/blob/main/func-adr/ADR-BCM-FUNC-0016-L2-SUP002-BEN-beneficiary-identity-anchor.md"
                "adr:ADR-TECH-TACT-002" "https://github.com/Banking-PapeeteConsulting/reliever-knowledge/blob/main/tech-adr/ADR-TECH-TACT-002-sup002-ben-beneficiary-identity-anchor.md"
                "adr:ADR-BCM-URBA-0001" "https://github.com/Banking-PapeeteConsulting/reliever-knowledge/blob/main/adr/ADR-BCM-URBA-0001-TOGAF-oriented-BCM-IS.md"
                "adr:ADR-BCM-URBA-0003" "https://github.com/Banking-PapeeteConsulting/reliever-knowledge/blob/main/adr/ADR-BCM-URBA-0003-1-capability-1-responsibility.md"
                "adr:ADR-BCM-URBA-0009" "https://github.com/Banking-PapeeteConsulting/reliever-knowledge/blob/main/adr/ADR-BCM-URBA-0009-event-capability-definition.md"
                "adr:ADR-BCM-URBA-0010" "https://github.com/Banking-PapeeteConsulting/reliever-knowledge/blob/main/adr/ADR-BCM-URBA-0010-L2-capabilities-as-urbanization-pivot.md"
                "adr:ADR-BCM-URBA-0012" "https://github.com/Banking-PapeeteConsulting/reliever-knowledge/blob/main/adr/ADR-BCM-URBA-0012-introduction-of-canonical-business-concept.md"
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
                "adr:ADR-DOM-0005" "https://github.com/Banking-PapeeteConsulting/reliever-knowledge/blob/main/domain-vision/adr/ADR-DOM-0005-dignity-as-functional-condition.md"
                "adr:ADR-DOM-0004" "https://github.com/Banking-PapeeteConsulting/reliever-knowledge/blob/main/domain-vision/adr/ADR-DOM-0004-tier-algorithm-prescriber-override.md"
                "adr:ADR-DOM-0006" "https://github.com/Banking-PapeeteConsulting/reliever-knowledge/blob/main/domain-vision/adr/ADR-DOM-0006-bypass-detection-unconsumed-envelope.md"
                "adr:ADR-DOM-0002" "https://github.com/Banking-PapeeteConsulting/reliever-knowledge/blob/main/domain-vision/adr/ADR-DOM-0002-primary-beneficiary-multi-prescriber.md"
                "adr:ADR-DOM-0003" "https://github.com/Banking-PapeeteConsulting/reliever-knowledge/blob/main/domain-vision/adr/ADR-DOM-0003-scope-open-banking-protocol.md"
                "adr:ADR-DOM-0001" "https://github.com/Banking-PapeeteConsulting/reliever-knowledge/blob/main/domain-vision/adr/ADR-DOM-0001-service-offer-framing.md"
            }
            backend = container "Backend microservice" "Backend microservice" "python+fastapi+postgresql · Mode A" {
                tags "implemented:mode-a" "tech:python+fastapi+postgresql"
                properties {
                    "loc" "sources/CAP.SUP.002.BEN/backend"
                    "github" "https://github.com/Banking-PapeeteConsulting/banking-reliever/blob/main/sources/CAP.SUP.002.BEN/backend"
                }
                AGG_SUP_002_BEN_IDENTITY_ANCHOR = component "IDENTITY ANCHOR" "Aggregate (DDD) — AGG.SUP.002.BEN.IDENTITY_ANCHOR" {
                    tags "ddd:aggregate"
                    properties { "id" "AGG.SUP.002.BEN.IDENTITY_ANCHOR" }
                }
                PRJ_SUP_002_BEN_ANCHOR_DIRECTORY = component "ANCHOR DIRECTORY" "Read model / CQRS — PRJ.SUP.002.BEN.ANCHOR_DIRECTORY" {
                    tags "ddd:read-model"
                    properties { "id" "PRJ.SUP.002.BEN.ANCHOR_DIRECTORY" }
                }
                PRJ_SUP_002_BEN_ANCHOR_HISTORY = component "ANCHOR HISTORY" "Read model / CQRS — PRJ.SUP.002.BEN.ANCHOR_HISTORY" {
                    tags "ddd:read-model"
                    properties { "id" "PRJ.SUP.002.BEN.ANCHOR_HISTORY" }
                }
                QRY_SUP_002_BEN_GET_ANCHOR = component "GET ANCHOR" "Read model / CQRS — QRY.SUP.002.BEN.GET_ANCHOR" {
                    tags "ddd:read-model"
                    properties { "id" "QRY.SUP.002.BEN.GET_ANCHOR" }
                }
                QRY_SUP_002_BEN_GET_ANCHOR_HISTORY = component "GET ANCHOR HISTORY" "Read model / CQRS — QRY.SUP.002.BEN.GET_ANCHOR_HISTORY" {
                    tags "ddd:read-model"
                    properties { "id" "QRY.SUP.002.BEN.GET_ANCHOR_HISTORY" }
                }
                EVT_SUP_002_BENEFICIARY_ANCHOR_UPDATED = component "BENEFICIARY ANCHOR UPDATED" "Business event publisher — EVT.SUP.002.BENEFICIARY_ANCHOR_UPDATED" {
                    tags "ddd:publisher"
                    properties { "id" "EVT.SUP.002.BENEFICIARY_ANCHOR_UPDATED" }
                }
            }
        }

        CAP_SUP_002_BEN_downstream_consumers = softwareSystem "Downstream consumers" "Any capability subscribed to the business events emitted by this one." {
            tags "external-capability"
        }
        CAP_SUP_002_BEN.backend -> CAP_SUP_002_BEN_downstream_consumers "BENEFICIARY ANCHOR UPDATED" "Business event" "downstream-event"
    }

    views {
        systemContext CAP_SUP_002_BEN "L2-Context" {
            include *
            autoLayout lr
        }
        container CAP_SUP_002_BEN "L2-Containers" {
            include *
            autoLayout lr
        }
        component CAP_SUP_002_BEN.backend "L2-Components-backend" {
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
