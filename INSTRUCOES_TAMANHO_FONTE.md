# Ajustar o tamanho das fontes do FMABC Eventos

No arquivo `static/app.css`, logo no início, há esta variável:

```css
:root{--fmabc-font-scale:1.10; ... }
```

Altere apenas o número para o tamanho desejado:

- `1.00` = tamanho original
- `1.05` = aumento de 5%
- `1.10` = aumento de 10% (padrão deste pacote)
- `1.15` = aumento de 15%
- `1.20` = aumento de 20%

As regras `font-size` do CSS foram ligadas a essa variável para manter a hierarquia tipográfica e escalar o texto da interface sem aumentar da mesma forma os espaçamentos, cartões e margens.

## Aplicar no Windows

1. Pare o servidor com `Ctrl+C`.
2. Faça uma cópia de segurança da pasta do projeto ou, no mínimo, de `static/app.css`.
3. Substitua `static/app.css` pelo arquivo deste pacote, mantendo a estrutura de pastas.
4. Inicie novamente com `set PORT=5055` e depois `python app.py`.
5. No navegador, atualize com `Ctrl+F5`.

O patch altera somente `static/app.css`. Não substitui nem altera `instance/fmabc_eventos.db` ou `.env`.
