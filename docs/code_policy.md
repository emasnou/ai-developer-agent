# 📜 Política de Codi, Estàndards i Seguretat

## 1. Nomenclatura i Estil (PEP8 & Clean Code)
- **Variables i funcions**: `snake_case` (ex: `generate_reset_token`).
- **Classes**: `PascalCase` (ex: `UserAuthenticationManager`).
- **Constants**: `UPPER_SNAKE_CASE` (ex: `TOKEN_EXPIRATION_MINUTES = 15`).
- **Noms descriptius**: Evitar abreviatures ambigües (ex: utilitzar `user_email` en lloc de `u_e`).

## 2. Estructura i Documentació
- **Docstrings**: Tota funció o classe ha de tenir docstrings en format Google o Sphinx explicant paràmetres i valors de retorn.
- **Tipat estàtic (Type Hints)**: Totes les signatures de funcions han d'incloure tipat (ex: `def get_user(user_id: int) -> dict:`).
- **Mida de funcions**: Les funcions no han de superar les 30-40 línies de codi i han de seguir el principi de responsabilitat única (SRP).

## 3. Rendiment (Performance)
- **Complexitat temporal**: Evitar bucles anidats innecessaris ($O(n^2)$) sobre col·leccions grans.
- **Gestió de memòria**: Utilitzar generadors (`yield`) per a processament de grans volums de dades.
- **Consultes / I/O**: Minimitzar crides repetides a APIs o bases de dades dins de bucles.

## 4. Seguretat (OWASP Top 10)
- **A01: Broken Access Control**: Verificar permisos abans d'executar accions sobre recursos.
- **A02: Cryptographic Failures**: Utilitzar algoritmes d'encriptació/hashing segurs (ex: `bcrypt`, `secrets` en lloc de `md5` o `random`).
- **A03: Injection (SQL/Command)**: Utilitzar consultes parametritzades; mai concatenar cadenes en comandes de sistema o SQL.
- **A04: Insecure Design**: Validar entrades de l'usuari rigorosament (`pydantic` o regex).
- **A05: Security Misconfiguration**: No exposar traces d'error o dades sensibles a les respostes de l'API.
- **A07: Identification & Authentication Failures**: Fórmules de recuperació de contrasenya sense revelar existència d'usuaris i amb tokens d'un sol ús i expiració breu.

## 5. Disseny de Proves i Aïllament (PyTest Best Practices)
- **Aïllament d'I/O (`tmp_path`)**: Els tests que generen fitxers o logs han d'utilitzar sempre la fixture `tmp_path` de pytest i no escriure a directoris arrel del projecte.
- **Eficiència en límits i rotació**: Per provar comportaments com la rotació de fitxers, limitar el paràmetre de mida (`maxBytes=500` o `1024`) per validar-lo en mil·lisegons, evitant escriure grans volums de dades en bucles lents.
- **Canvis Mínims en Components Existents**: Modificar exclusivament les línies necessàries en fitxers existents per incorporar noves funcionalitats, preservant totes les signatures i implementacions prèvies.

