// Generated four-scene stationery atlas; decorations never stand in for user data.
export function emptyArt(kind='journal'){
 const art=document.createElement('span');art.className='y-empty-art y-empty-'+kind;art.setAttribute('aria-hidden','true');return art;
}
