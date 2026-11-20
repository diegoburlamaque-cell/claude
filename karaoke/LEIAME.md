# Fila do Karaokê

App de fila para karaokê que roda no seu celular e é acessado pelos convidados na mesma rede Wi-Fi. Não precisa de internet.

## Android (Termux)
1. Instale o **Termux** pelo F-Droid (a versão da Play Store está desatualizada).
2. No Termux:
   ```
   pkg install python curl
   curl -LO https://raw.githubusercontent.com/diegoburlamaque-cell/claude/ccr-0a1c0921-bse62b/karaoke/fila_karaoke.py
   termux-wake-lock
   python fila_karaoke.py
   ```
3. A tela mostra o endereço dos convidados (ex.: `http://192.168.0.15:8000`) e o PIN do palco.

## Uso
- **Convidados** abrem o endereço no navegador, digitam o nome (e a música, se quiserem) e entram no fim da fila.
- **Você** abre `.../palco` no seu navegador, digita o PIN e toca em **OK, próximo** quando a pessoa terminar de cantar.
- **Tirar** remove quem foi embora. **Desfazer** volta o último removido.
- A fila fica salva em `fila.json`; se o app fechar, é só rodar de novo.
- PIN fixo: `PIN=1234 python fila_karaoke.py`.

## Se os convidados não conseguirem abrir
- Confira se estão na mesma rede Wi-Fi.
- Alguns roteadores (de visitante, de hotel) bloqueiam a conexão entre aparelhos. Use o **roteador do seu celular** e peça para todos se conectarem nele.
