// LottoMirato - Analisi Ritardi (JavaScript)
// Conversione 1:1 da analisi_ritardi.py

const RUOTE_NOMI = {
    BA:"Bari", CA:"Cagliari", FI:"Firenze", GE:"Genova",
    MI:"Milano", NA:"Napoli", PA:"Palermo", RM:"Roma",
    TO:"Torino", VE:"Venezia", RN:"Nazionale"
};

function caricaStorico(testo) {
    const estrazioni = [];
    for (const line of testo.split('\n')) {
        const trimmed = line.trim();
        if (!trimmed) continue;
        const parts = trimmed.split('\t');
        if (parts.length < 7) continue;
        estrazioni.push({
            data: parts[0],
            ruota: parts[1],
            numeri: [parseInt(parts[2]), parseInt(parts[3]), parseInt(parts[4]), parseInt(parts[5]), parseInt(parts[6])]
        });
    }
    return estrazioni;
}

function ottieniDateUniche(estrazioni) {
    return [...new Set(estrazioni.map(e => e.data))].sort();
}

function calcolaRitardi(estrazioni, ruotaFiltro) {
    const perRuota = {};
    for (const e of estrazioni) {
        if (!perRuota[e.ruota]) perRuota[e.ruota] = [];
        perRuota[e.ruota].push(e);
    }
    const risultati = {};
    const ruote = ruotaFiltro ? [ruotaFiltro] : Object.keys(perRuota);
    for (const ruota of ruote) {
        const estrRuota = (perRuota[ruota] || []).sort((a, b) => a.data.localeCompare(b.data));
        const ritardi = {};
        for (let num = 1; num <= 90; num++) {
            let ultimaUscita = null;
            for (let i = estrRuota.length - 1; i >= 0; i--) {
                if (estrRuota[i].numeri.includes(num)) { ultimaUscita = i; break; }
            }
            ritardi[num] = ultimaUscita !== null ? estrRuota.length - 1 - ultimaUscita : estrRuota.length;
        }
        risultati[ruota] = {
            ritardi,
            totale_estrazioni: estrRuota.length,
            ultima_data: estrRuota.length > 0 ? estrRuota[estrRuota.length - 1].data : "N/A"
        };
    }
    return risultati;
}

function calcolaRitardoMedio(estrazioni, ruota, numero) {
    const perRuota = estrazioni.filter(e => e.ruota === ruota).sort((a, b) => a.data.localeCompare(b.data));
    const uscite = perRuota.filter(e => e.numeri.includes(numero)).length;
    const totale = perRuota.length;
    if (uscite === 0) return { media: totale, uscite: 0, totale };
    return { media: totale / uscite, uscite, totale };
}

function calcolaRitardoMaxStorico(estrazioni, ruota, numero) {
    const perRuota = estrazioni.filter(e => e.ruota === ruota).sort((a, b) => a.data.localeCompare(b.data));
    let maxRitardo = 0, ritardoCorrente = 0;
    for (const e of perRuota) {
        if (e.numeri.includes(numero)) {
            if (ritardoCorrente > maxRitardo) maxRitardo = ritardoCorrente;
            ritardoCorrente = 0;
        } else { ritardoCorrente++; }
    }
    if (ritardoCorrente > maxRitardo) maxRitardo = ritardoCorrente;
    return maxRitardo;
}

function topRitardi(estrazioni, ruota, topN = 20) {
    const rit = calcolaRitardi(estrazioni, ruota);
    if (!rit[ruota]) return [];
    return Object.entries(rit[ruota].ritardi)
        .map(([num, r]) => ({ numero: parseInt(num), ritardo: r }))
        .sort((a, b) => b.ritardo - a.ritardo)
        .slice(0, topN);
}

function generaSuggerimenti(estrazioni) {
    const ruoteAnalisi = ["BA","CA","FI","GE","MI","NA","PA","RM","TO","VE"];
    const candidati = [];
    for (const ruota of ruoteAnalisi) {
        const ritData = calcolaRitardi(estrazioni, ruota);
        if (!ritData[ruota]) continue;
        const ritardi = ritData[ruota].ritardi;
        const ordinati = Object.entries(ritardi).map(([n, r]) => ({ numero: parseInt(n), ritardo: r }))
            .sort((a, b) => b.ritardo - a.ritardo);
        if (ordinati.length < 2) continue;
        const leader = ordinati[0], second = ordinati[1];
        const mL = calcolaRitardoMedio(estrazioni, ruota, leader.numero);
        const mS = calcolaRitardoMedio(estrazioni, ruota, second.numero);
        const maxL = calcolaRitardoMaxStorico(estrazioni, ruota, leader.numero);
        const maxS = calcolaRitardoMaxStorico(estrazioni, ruota, second.numero);
        const rapportoL = mL.media > 0 ? leader.ritardo / mL.media : 0;
        const rapportoS = mS.media > 0 ? second.ritardo / mS.media : 0;
        const pctVsMaxL = maxL > 0 ? leader.ritardo / maxL * 100 : 0;
        let forza = (rapportoL + rapportoS) / 2;
        if (pctVsMaxL >= 90) forza *= 1.3;
        if (rapportoL >= 2.5) {
            candidati.push({
                ruota, ruota_nome: RUOTE_NOMI[ruota] || ruota,
                leader: { numero: leader.numero, ritardo: leader.ritardo, media: Math.round(mL.media * 10) / 10, rapporto: Math.round(rapportoL * 100) / 100, max_storico: maxL, pct_vs_max: Math.round(pctVsMaxL * 10) / 10, uscite: mL.uscite },
                secondario: { numero: second.numero, ritardo: second.ritardo, media: Math.round(mS.media * 10) / 10, rapporto: Math.round(rapportoS * 100) / 100, max_storico: maxS, pct_vs_max: Math.round(maxS > 0 ? second.ritardo / maxS * 100 * 10 : 0) / 10, uscite: mS.uscite },
                forza: Math.round(forza * 100) / 100,
                ambo: [leader.numero, second.numero],
                estratto: leader.numero
            });
        }
    }
    return candidati.sort((a, b) => b.forza - a.forza);
}

function verificaVincita(dataEstr, estrazioni, giocata) {
    const risultati = {};
    for (const [ruotaCode, g] of Object.entries(giocata)) {
        const ruotaNome = RUOTE_NOMI[ruotaCode] || ruotaCode;
        const estrazione = estrazioni.find(e => e.data === dataEstr && e.ruota === ruotaCode);
        if (!estrazione) { risultati[ruotaCode] = { ruota_nome: ruotaNome, trovata: false }; continue; }
        const numeri = estrazione.numeri;
        risultati[ruotaCode] = {
            ruota_nome: ruotaNome, trovata: true, numeri_usciti: numeri,
            estratto_presente: numeri.includes(g.estratto),
            ambo_vinto: g.ambo.every(n => numeri.includes(n)),
            singoli_presenti: g.ambo.filter(n => numeri.includes(n))
        };
    }
    return risultati;
}
