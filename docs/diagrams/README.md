# Architecture Diagrams

This directory is reserved for architecture diagrams.

## Adding Diagrams

Add diagrams in formats supported by GitHub/GitLab rendering:
- **Mermaid** (`.mermaid`, `.mmd`) - preferred
- **PlantUML** (`.puml`)
- **SVG** (`.svg`) - preferred for complex diagrams
- **PNG** (`.png`) - raster format

## Diagram Sources

Architecture diagrams should be added manually or generated from source:
- Pipeline flow: `stages/` directory structure
- Data flow: `contracts/` directory structure

## Request

If you need to add diagrams:
1. Create a `.mermaid`, `.puml`, `.svg`, or `.png` file
2. Reference it from `../current/ARCHITECTURE.md`
3. Commit with the related documentation change
