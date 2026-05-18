workspace "Zone REFERENTIAL" "C4 container view of the REFERENTIAL zone — each L2 capability is a container." {

    !identifiers hierarchical

    model {
        zone_REF = softwareSystem "REFERENTIAL" "REFERENTIAL zone of the Reliever business capability model." {
            tags "capability-self" "zone:REF"
            CAP_REF_001_PRE = container "CAP.REF.001.PRE" "Prescriber Referential" "stack-tbd" {
                tags "not-scaffolded" "tech:stack-tbd" "parent:CAP.REF.001"
                properties {
                    "detail-view" "../CAP.REF.001.PRE/workspace.dsl"
                    "parent" "CAP.REF.001"
                }
            }
            CAP_REF_001_TIE = container "CAP.REF.001.TIE" "Tier Referential" "stack-tbd" {
                tags "not-scaffolded" "tech:stack-tbd" "parent:CAP.REF.001"
                properties {
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
