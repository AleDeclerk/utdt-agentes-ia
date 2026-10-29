# Prerrequisitos reales — Curso de Arquitectura de Agentes IA (UTDT 2026)

> Este documento describe los conocimientos previos que el curso efectivamente requiere, basado en el contenido real de los 13 módulos (slides, guiones y labs) y en la naturaleza de los ejercicios prácticos. No es un listado aspiracional: refleja lo que hace falta para poder seguir las clases y completar los labs sin quedar bloqueado.

La curricula oficial es explícita en este punto: **"No se trata de un curso introductorio; es una inmersión profunda en la ingeniería de sistemas que actúan de manera autónoma en entornos complejos y dinámicos."**

---

## Imprescindibles

### Python intermedio/avanzado
No alcanza con sintaxis básica. Los labs (especialmente módulos 4 a 8) usan `async`/`await`, decoradores, type hints y manejo de excepciones de forma constante. Sin este nivel, buena parte de los ejercicios prácticos son inabordables.

### APIs, HTTP y JSON
Los labs consumen APIs REST, configuran API keys y trabajan con schemas JSON para definir tools. No se requiere experiencia de backend developer, pero sí haber integrado alguna API externa previamente.

### Línea de comandos y control de versiones (git)
Instalación de paquetes vía `pip`, manejo de variables de entorno (`.env`), navegación y estructura de un repositorio.

### Qué es un LLM y cómo se usa vía prompt/API
Nivel usuario avanzado, no investigador. El curso **no** explica desde cero qué es un transformer ni el pretraining a nivel matemático — lo asume como base y construye sobre eso desde el Módulo 1.

---

## Deseables (no bloqueantes)

### Docker básico
El módulo de observabilidad (monitoreo en producción) usa un stack Loki + Tempo + Grafana en contenedores. Quien nunca corrió `docker compose up` va a perder tiempo específicamente en esa parte, sin que afecte el resto del curso.

### Nociones de arquitectura de software
Interfaces, modularidad, patrones de diseño. Ayuda mucho en los módulos de diseño de sistemas y orquestación multiagente (Módulos 2, 5 y 8), pero se explican en el curso a medida que se necesitan.

### Haber tocado fine-tuning o ML supervisado alguna vez, aunque sea superficialmente
El Módulo 7 (SFT / DPO / RLVR con TRL, PEFT y LoRA) es aplicado, no teórico — no se deriva el algoritmo matemático, pero si nunca se vio qué significa "entrenar" un modelo, es un salto conceptual grande en una sola clase.

---

## Lo que NO hace falta

Para no exagerar el nivel requerido:

- Matemática de deep learning ni álgebra lineal aplicada a redes neuronales.
- Haber entrenado un modelo desde cero.
- Experiencia previa con **LangGraph** o **Google ADK2** específicamente — ambos frameworks se enseñan desde los Módulos 1 y 2.
- Experiencia en ciberseguridad para el Módulo 12 (protección de sistemas agénticos) — se cubre a nivel de principios aplicados, no pentesting ni red teaming.

---

*Elaborado a partir del contenido de `SLIDES_v2/modulo_01..13/` (slides, guiones y labs) y de `Curricula_v2.docx`.*
