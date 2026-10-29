# Módulo 01 — Python intermedio/avanzado

## Por qué hace falta

Los labs de los módulos 4 a 8 del curso (tool use, orquestación, memoria, aprendizaje, multiagente) usan `async`/`await` de forma constante para llamar a agentes y herramientas, decoradores para registrar tools, y type hints para definir schemas que el modelo usa para invocar funciones. No es Python de scripting simple.

## Autodiagnóstico

Respondé sin buscar en internet. Si dudás en 2 o más, conviene repasar:

1. ¿Sabés qué hace `async def` y por qué una función `async` no se puede llamar como una función normal?
2. ¿Entendés la diferencia entre `await algo()` y simplemente `algo()`?
3. ¿Sabés escribir un decorador propio con `@mi_decorador` (no solo usar uno ya hecho)?
4. ¿Sabés qué significa `def foo(x: int) -> str:` y por qué se usa aunque Python no lo obligue en runtime?
5. ¿Manejaste alguna vez `try/except` con excepciones específicas (no un `except:` genérico)?

## Si hay brechas: recursos gratuitos

**Async/await**
- Documentación oficial: https://docs.python.org/3/library/asyncio-task.html
- Real Python, "Async IO in Python: A Complete Walkthrough": https://realpython.com/async-io-python/

**Decoradores**
- Real Python, "Primer on Python Decorators": https://realpython.com/primer-on-python-decorators/

**Type hints**
- Documentación oficial: https://docs.python.org/3/library/typing.html
- Real Python, "Python Type Checking": https://realpython.com/python-type-checking/

**Repaso general de Python intermedio** (si las brechas son varias a la vez)
- freeCodeCamp, curso de Python (gratuito, con certificado): https://www.freecodecamp.org/learn/scientific-computing-with-python/

## Tiempo estimado

4-8 horas si hay que repasar los tres temas (async, decoradores, type hints) desde una base de Python básico ya sólida.
