import { Config } from './config.interface';

/**
 * Configurações customizadas
 */
export class AcessoAcademicoConfig implements Config {

    logotipo: string;

    titulo: string;

    subTitulo: string;

    itemPage: {
        // Metadados extras exibidos na página simplificada (após os campos padrão)
        metadadosAdicionais: { campos: string[]; label: string; separador?: string }[];
        // Labels da página completa (/full); campo ausente = exibe o nome técnico
        labelsMetadados: { [campo: string]: string };
    };

}
