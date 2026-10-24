/**
 * Design system do Ponto.
 *
 * Ponto de entrada unico: as telas importam daqui, nunca de um arquivo solto.
 *
 *   import { Botao, Cartao, Texto, cores, espaco, raio } from '../ui';
 *
 * Os tokens (cores, espaco, tipo, raio, toque) continuam morando em theme.ts
 * e sao reexportados aqui — assim `../theme` segue funcionando nas telas que
 * ainda nao migraram, sem import duplicado.
 */
export { cores, espaco, tipo, raio, toque } from '../theme';

export { Texto } from './Texto';
export type { TextoProps } from './Texto';

export { Botao } from './Botao';
export { Cartao } from './Cartao';
export { Campo } from './Campo';
export type { CampoProps } from './Campo';
export { Linha } from './Linha';
export { Pilula } from './Pilula';
export { PontoStatus, corDoEstado } from './PontoStatus';
export type { EstadoPonto } from './PontoStatus';
