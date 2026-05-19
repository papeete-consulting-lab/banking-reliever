workspace "Zone — Referential" "C4 container view of the Referential zone — each L2 capability is a container." {

    !identifiers hierarchical

    model {
        zone_REF = softwareSystem "Referential" "Referential zone of the Reliever business capability model." {
            tags "capability-self" "zone:REF"
            properties {
                "zone-code" "REFERENTIAL"
            }
            CAP_REF_001_PRE = container "Prescriber Referential" "Hold and maintain the canonical identity of prescribers and their organisations. Distinguishes prescriber types (banker, doctor, social worker) and their respective authorisations within the programme." "stack-tbd" {
                tags "not-scaffolded" "tech:stack-tbd" "parent:CAP.REF.001"
                properties {
                    "capability-id" "CAP.REF.001.PRE"
                    "detail-view" "../CAP.REF.001.PRE/workspace.dsl"
                    "parent" "CAP.REF.001"
                }
            }
            CAP_REF_001_TIE = container "Tier Referential" "Hold and maintain the canonical tier definitions: usage rules, transition thresholds, associated rights. Any modification goes through this L2 and triggers Tier.DefinitionUpdated, consumed in cascade by BSP.001, BSP.004 and B2B.001." "stack-tbd" {
                tags "not-scaffolded" "tech:stack-tbd" "parent:CAP.REF.001"
                properties {
                    "capability-id" "CAP.REF.001.TIE"
                    "detail-view" "../CAP.REF.001.TIE/workspace.dsl"
                    "parent" "CAP.REF.001"
                }
            }
        }
    }

    views {
        systemContext zone_REF "Zone-Context" {
            include *
            autoLayout lr
        }
        container zone_REF "Zone-Containers" {
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
