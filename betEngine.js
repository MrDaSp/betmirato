// Motore Predittivo BetMirato (Distribuzione di Poisson)

// Fattoriale per formula di poisson
function fattoriale(k) {
    if (k === 0 || k === 1) return 1;
    let res = 1;
    for (let i = 2; i <= k; i++) res *= i;
    return res;
}

// Probabilità esatta di segnare K gol se ci si aspetta Lambda gol
function poisson(k, lambda) {
    return (Math.exp(-lambda) * Math.pow(lambda, k)) / fattoriale(k);
}

// Calcola le percentuali finali (1X2, U/O, GG/NG) in base agli Expected Goals
function calcolaProbabilita(lambdaHome, lambdaAway) {
    let prob = { '1': 0, 'X': 0, '2': 0, 'U25': 0, 'O25': 0, 'GG': 0, 'NG': 0 };
    
    // Matrice punteggi esatti (0-0 fino a 5-5 che copre il 99% della densità)
    for(let h = 0; h <= 5; h++) {
        for(let a = 0; a <= 5; a++) {
            let p_h = poisson(h, lambdaHome);
            let p_a = poisson(a, lambdaAway);
            let p_matrix = p_h * p_a;
            
            // 1X2
            if (h > a) prob['1'] += p_matrix;
            else if (h === a) prob['X'] += p_matrix;
            else prob['2'] += p_matrix;
            
            // Under / Over 2.5
            if (h + a < 2.5) prob['U25'] += p_matrix;
            else prob['O25'] += p_matrix;
            
            // Gol / No Gol
            if (h > 0 && a > 0) prob['GG'] += p_matrix;
            else prob['NG'] += p_matrix;
        }
    }
    
    // Scala percentuale
    for(let key in prob) {
        prob[key] = (prob[key] * 100).toFixed(2);
    }
    return prob;
}

// Confronta le nostre Probabilità Reali con le quote offerte (Sisal) e genera il semaforo
function analizzaValueBetSemaforo(quotaBookmaker, probabilitaReale) {
    if (!quotaBookmaker || quotaBookmaker <= 1) return null;
    
    let impliedProb = 100 / quotaBookmaker;
    let vantaggio = probabilitaReale - impliedProb;
    
    if (vantaggio >= 5.0) {
        return { colore: '#2ecc71', status: 'VERDE (Alta Value Bet)', vantaggio: vantaggio.toFixed(1) };
    } else if (vantaggio > 0.0) {
        return { colore: '#f1c40f', status: 'GIALLA (Margine Lieve)', vantaggio: vantaggio.toFixed(1) };
    } else {
        return { colore: '#e74c3c', status: 'ROSSA (Trappola - Quota Pompata)', vantaggio: vantaggio.toFixed(1) };
    }
}
