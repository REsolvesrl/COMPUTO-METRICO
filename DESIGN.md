# Design

<!-- impeccable:design-schema 1 -->

Mondo visivo di CME: **Campionario**. Le regole durature; i valori esatti
vivono in `.streamlit/config.toml` e in `css_schede_computo()`.

## Il mondo

Un campionario di materiali edili: le cartelle di campioni che un tecnico
sfoglia in showroom per scegliere le finiture. Tinte piene e sature, etichette
piccole in maiuscoletto spaziato, un codice accanto a ogni cosa, e il pezzo
vero — la planimetria — appoggiato su un piano da lavoro.

Ciò che il mondo **rifiuta**: il gestionale bianco a schede arrotondate con
accento blu, e il suo opposto altrettanto scontato, lo scuro con i neon.

## Colore

**Strategia: Committed.** L'ardesia scura copre la superficie, i materiali
saturi portano tutto il resto. Il colore non è decorazione aggiunta sopra: è
la materia di cui l'app parla.

| Ruolo | Materiale | Valore |
|---|---|---|
| Fondo (il banco) | Ardesia | `#1A2744` |
| Fondo rialzato (il campione) | Ardesia chiara | `#243352` |
| Accento primario, azioni | Ottone | `#C9A96A` |
| Testo su scuro | Travertino | `#ECE7DA` |
| Materia calda, avvisi | Cotto | `#C1502E` |
| Materia fredda, quiete | Cemento | `#6E7377` |
| Conferme | Gres verde | `#4E7A5E` |

Ardesia e ottone vengono dal logo Resolve: nel campionario diventano due
materiali fra gli altri, la pietra e il metallo. Il marchio non è appiccicato
sopra il mondo, ne fa parte.

⚠️ **I colori delle categorie di superficie non appartengono a questo
sistema.** Verde giardino, giallo terrazzo, azzurro vano scale e gli altri
(`COLORE_CATEGORIA_SUP`) sono **segnali di significato**, scelti dall'utente
per distinguere le zone sul disegno. Il mondo governa la cornice; quei colori
governano il contenuto e non si toccano per ragioni estetiche.

⚠️ **Nemmeno i colori dei sette mestieri appartengono al campionario, e
restano così per scelta.** `COLORI_CATEGORIE` — rosso Demolizioni, verde
Ricostruzioni, azzurro Idraulico, arancio Elettricista, viola Serramenti —
sono tinte da tavolozza generica, non cotto/gres/cemento, e stanno sulla
scheda del computo, cioè dentro la cornice e non sul disegno. La deroga qui
sopra, scritta per il disegno, **non** li copriva: la si estende adesso,
consapevolmente, perché sono i colori con cui l'utente distingue i mestieri
a colpo d'occhio da prima dell'app. Vale una regola sola: **la tinta vive
nella pastiglia**, non nel titolo. Il nome della categoria si legge in
travertino, e quando Streamlit non ha un token che corrisponda alla tinta
(le due categorie «grigie») il titolo non si colora affatto — il grigio di
Streamlit è `rgba(250,250,250,.6)` e accanto a cinque tinte piene non legge
«grigio», legge «disattivato».

Chi un giorno volesse riportarli dentro al mondo sappia che è una decisione
di prodotto, non un abbellimento: cotto per Demolizioni, gres per
Ricostruzioni, cemento per Aree esterne, travertino per Pratiche. Non farlo
di propria iniziativa.

## Tipografia

Pile di sistema, nessun carattere scaricato dalla rete: **il programma deve
funzionare con la connessione staccata**, e un font che non arriva è una
pagina che si ridisegna sotto gli occhi.

- Interfaccia e testo: `Segoe UI Variable Text, Segoe UI, system-ui, sans-serif`
- Numeri (quantità, prezzi, superfici): stessa pila con
  `font-variant-numeric: tabular-nums` — le cifre incolonnate sono un
  requisito, non un vezzo: qui si confrontano importi.
- **Etichetta campione**: 0,7 rem, maiuscoletto, `letter-spacing: .12em`.
  È la voce del sistema: nomina categorie, unità, codici. Non usarla per
  frasi. ⚠️ **Il cemento pieno su ardesia sta a 3,1:1**, sotto la soglia di
  leggibilità proprio nella riga che nomina le cose: si schiarisce col
  travertino (`color-mix(in srgb, var(--travertino) 78%, var(--cemento))`).
  Resta la voce del cemento, ma si legge.

## Componenti

- **Campione** (la scheda): fondo della propria tinta al 15%, contorno della
  stessa tinta al 60%, ed **è la tinta a occupare una superficie** — la
  pastiglia piena del materiale, almeno 44 px, oppure il fondo intero della
  scheda. Etichetta campione in alto, numero grande in basso a destra.
  ⚠️ **Mai una banda sottile sul bordo sinistro**: è l'abitudine del
  gestionale travestita da campionario. Un campione vero è una tinta che si
  guarda, non una riga che decora.
  Applicato alle categorie del computo: la pastiglia è `button::before`
  (44 px di tinta piena), l'etichetta col codice è
  `[data-testid="stMarkdownContainer"]::before` e il totale è
  `button::after`. Nell'etichetta di un bottone Streamlit ci sta una sola
  riga di testo, e dev'essere un unico nodo — la freccia va dentro la
  marcatura di colore, altrimenti diventa un secondo elemento della griglia
  e finisce a capo.
- **Metrica**: ogni `st.metric` è un campione — etichetta in maiuscoletto
  sopra, numero grande sotto, fondo rialzato e squadrato. Vale in tutta
  l'app: planimetria, riepilogo del computo, business plan.
- **Il numero che comanda una scheda è ottone pieno**, tinta su tutta la
  superficie e cifra in ardesia: il totale finale del computo, i costi
  totali dell'operazione. Uno per scheda, altrimenti non comanda più.
- **Azioni**: ottone pieno per l'azione principale, contorno ottone per le
  secondarie, mai due azioni piene affiancate.
- **Il disegno comanda**: nella scheda planimetria la tela ha la larghezza
  intera e il contrasto più alto della pagina — sta su un piano da lavoro
  (`st.container(key="tela")`: fondo rialzato, contorno d'ottone). Pannelli
  e comandi stanno attorno in cemento, mai in competizione: i gruppi di
  campi vivono in contenitori `pan_*` col contorno di cemento, che
  raggruppano invece di allineare una fila indistinta di caselle.
- **Stati vuoti**: sono una cartella di campioni aperta, non un riquadro
  grigio con una frase. Dicono cosa succede dopo, con l'azione a portata.

## Regole durature

1. **Tinte piene, mai fotografie di materiali.** Il campionario è di tinte, non
   di texture: una foto di gres su una tabella di numeri la rende illeggibile.
2. **Ogni cosa ha la sua etichetta e il suo codice**, come un campione vero:
   le voci di listino mostrano il codice, le superfici l'unità, le categorie
   la percentuale.
3. **Niente ombre diffuse per fingere profondità.** La profondità viene dal
   bordo del materiale e dal fondo rialzato.
4. **Il numero è il protagonista.** In ogni scheda il valore è l'elemento più
   grande dopo il titolo.
5. **Un solo ritmo di spaziatura**, con più aria sopra un titolo che sotto.
6. **Vincolo Streamlit da conoscere:** le tabelle modificabili
   (`st.data_editor`) sono disegnate su tela grafica e **ignorano il CSS**.
   Non provare a vestirle: il colore arriva accanto (pallini, campioni,
   riepiloghi in HTML). Ci abbiamo già sbattuto la testa con i colori delle
   categorie di spesa.
