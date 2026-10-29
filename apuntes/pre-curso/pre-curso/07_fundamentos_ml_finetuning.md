# Módulo 07 — Fundamentos de ML supervisado / fine-tuning (deseable)

## Por qué hace falta

El módulo 7 del curso (aprendizaje en sistemas agénticos) cubre SFT, DPO y RLVR usando librerías de alto nivel (TRL, PEFT, LoRA). Es aplicado, no teórico — no se deriva el algoritmo matemático de backpropagation ni de optimización. Pero si nunca se vio qué significa "entrenar" un modelo con datos etiquetados, ese módulo es un salto conceptual grande en una sola clase.

## Autodiagnóstico

1. ¿Entendés la diferencia entre entrenar un modelo y usarlo en inferencia?
2. ¿Sabés qué es un dataset etiquetado y por qué hace falta uno para "supervised fine-tuning"?
3. ¿Tenés una intuición de qué significa que un modelo "aprenda una preferencia" a partir de pares de respuestas (una mejor que otra)? — esto es la idea detrás de DPO.
4. ¿Escuchaste hablar de fine-tuning eficiente (LoRA / adaptadores) y por qué existe como alternativa a reentrenar todo el modelo?

## Si hay brechas: recursos gratuitos

**Curso gratuito y aplicado, con certificado**
- Hugging Face, "NLP Course" (cubre fine-tuning de forma práctica): https://huggingface.co/course

**Fine-tuning con LoRA/PEFT, documentación oficial**
- Hugging Face, documentación de PEFT: https://huggingface.co/docs/peft/index

**DPO, explicación conceptual**
- Hugging Face, documentación de TRL sobre DPO: https://huggingface.co/docs/trl/dpo_trainer

## Tiempo estimado

3-6 horas. No hace falta completar el curso de Hugging Face entero — con las primeras secciones (qué es fine-tuning, cómo se prepara un dataset) y una lectura de la documentación de PEFT alcanza como base para el módulo del curso.
