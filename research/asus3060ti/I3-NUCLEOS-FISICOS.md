# i3-10100: investigação de núcleos físicos adicionais

Data: 2026-10-29. Objetivo corrigido pelo usuário: **reativar núcleos físicos desativados pela Intel**, se existirem e forem recuperáveis. Ajustar threads, Hyper-Threading, turbo ou afinidade não atende esse objetivo. Os benchmarks anteriores não são evidência de unlock de núcleos.

## Conclusão desta rodada

Há uma pista plausível de família de silício compartilhada, mas **não foi demonstrado um caminho para habilitar o quinto ou sexto núcleo deste i3-10100**. Não há evidência de integridade dos blocos não expostos, mapa de fuses desta unidade ou override funcional. Isso é uma hipótese de pesquisa sem garantia de retorno, não uma função disponível para automatizar.

O inventário atual confirmou i3-10100, assinatura `000A0653`, quatro núcleos físicos habilitados e oito processadores lógicos. O objetivo aqui seria observar mais de quatro núcleos físicos capazes de executar trabalho independente, não fazer o Windows mostrar mais entradas.

## Evidências primárias

1. Intel, *10th Generation Intel Core Processor Specification Update*, documento **615213**, página PDF 7 (página impressa 7): a tabela identifica **S 6+2 G-1**, **S 4+2 G-1**, **S 2+2 G-1** e **S 2+1 G-1** com a mesma assinatura `A0653h`. Portanto, CPUID compartilhado não distingue quantos blocos físicos permanecem disponíveis em uma unidade. `+2` não significa dois núcleos CPU adicionais.
2. Intel, *Datasheet Volume 1*, documento **615211**, página PDF 136: agrupa `CML S6/S4/S2-Core G1` sob `A0653h`. Corrobora a família comum; não comprova capacidade de reativação. A página PDF 137 enumera IDs de host bridge distintos para SKUs S6/S4/S2; mudar um identificador PCI não cria capacidade física.
3. Intel, repositório oficial de microcódigo, commit `bdc92abe5c499c3fd7988b76a128d05c9120a520`, `releasenote.md`, linha 368: associa `06-a5-03/22` a `CML-S62`, stepping `G1`. Essa associação reforça a hipótese do projeto compartilhado de seis núcleos, mas não permite inferir quais núcleos estariam íntegros no exemplar. A tabela detalhada do item 1 impede tratar o nome da família como contagem física confirmada.
4. IntelFsp/FSP, commit `d901c9458288e1a0eb0ec9901efcd2ddfaa01cb8`, `CometLakeFspBinPkg/CometLakeS/Include/FspmUpd.h`, linhas 928–933: campo `ActiveCoreCount`, opção `0: All`. O cabeçalho descreve seleção de núcleos ativos; **não descreve override do limite de núcleos do SKU**. A existência do campo não prova que escrever 5 ou 6 funcione, nem que esse pacote seja exatamente o componente embutido na BIOS ASUS 1806.
5. O mesmo pacote, `FspsUpd.h`, inclui limites de turbo para até oito núcleos. São parâmetros de uma família de produtos; a presença do campo `SixCoreRatioLimit` não demonstra seis núcleos disponíveis nesta CPU. Turbo não altera a contagem.
6. Intel, *Datasheet Volume 2*, documento **615212**, 395 páginas: a busca textual desta rodada não encontrou um mecanismo descrito de reativação usando os termos `CORE_DISABLE`, `CORE_THREAD_COUNT`, active core e core/fuse. Isso é um resultado limitado de busca textual, não prova de ausência de mecanismo interno.

Os três PDFs e os dois cabeçalhos foram baixados apenas para análise estática local. Nenhum deles foi executado ou gravado em firmware. Hashes e URLs constam em [evidence/cpu-physical-core-sources.json](evidence/cpu-physical-core-sources.json); os documentos não são redistribuídos neste diretório.

## Caminhos a distinguir

| Hipótese | O que precisaria ser provado | Resultado atual |
|---|---|---|
| Núcleos do SKU ocultos por BIOS/Windows | Quatro especificados, mas menos de quatro ativos | Não explica este caso: quatro já ativos |
| Die maior com blocos íntegros desativados | Identificação física confiável do die e estado de cada bloco | Família compartilhada plausível; integridade individual desconhecida |
| Máscara reversível antes da inicialização | Registro/máscara exatos para G1 e fluxo que aceite ultrapassar quatro | Campo público de seleção localizado; nenhum override demonstrado |
| Limite imposto por fuses de fabricação | Mapa correto e distinção entre leitura de fuse, política firmware e sinal interno | Não medido nesta unidade; não presumir que registro de status seja gravável |
| Firmware/microcódigo substituível | Vulnerabilidade/override demonstrado para esse stepping, com validação física | Nenhum identificado nesta rodada; editar bytes arbitrariamente não é método |
| Interface de teste/debug | Acesso real e autorização de depuração compatível com chip de produção | Não estabelecido. A documentação pública de debug não demonstra ativação de núcleos fundidos |
| Modificação física | Topologia exata, possibilidade de acesso e prova independente de reversibilidade | Sem evidência e fora dos testes de software desta rodada |

## Próxima investigação que pode alterar a conclusão

- Analisar estaticamente a imagem oficial **exata** da ASUS PRIME B460-PLUS BIOS 1806: formulário `Active Processor Cores`, variáveis, caminho até CPU init e versão dos componentes. Ainda não foi obtida/analisada nesta rodada. Encontrar menu oculto sozinho não prova unlock.
- Procurar documentação ou pesquisa original que mapeie a máscara de disponibilidade/fuses para **Comet Lake-S G1**. Não reutilizar endereços de Atom, Xeon ou outra geração.
- Só elaborar uma coleta de registradores quando endereços, semântica, acesso e efeitos estiverem estabelecidos. CPUID/APIC/ACPI mostram topologia exposta; não atestam a integridade de blocos desligados.
- Um futuro teste de habilitação exigiria procedimento específico e reversível, prova de inicialização do núcleo extra e execução numérica/estabilidade por núcleo. Alterar strings, CPUID ou entradas ACPI não conta como sucesso.
- Se o único caminho restante exigir acesso interno não disponível ou não produzir sinal novo em um teste pequeno, registrar a limitação e avançar a outra frente sem apresentar hipótese como desbloqueio.

## Fontes

- [Intel 615213](https://cdrdv2.intel.com/v1/dl/getContent/615213)
- [Intel 615211](https://cdrdv2.intel.com/v1/dl/getContent/615211)
- [Intel 615212](https://cdrdv2.intel.com/v1/dl/getContent/615212)
- [Notas oficiais de microcódigo, versão fixada](https://github.com/intel/Intel-Linux-Processor-Microcode-Data-Files/blob/bdc92abe5c499c3fd7988b76a128d05c9120a520/releasenote.md)
- [Intel FSP, controle de núcleos, versão fixada](https://github.com/IntelFsp/FSP/blob/d901c9458288e1a0eb0ec9901efcd2ddfaa01cb8/CometLakeFspBinPkg/CometLakeS/Include/FspmUpd.h#L928)
- [Intel: capacidades e restrições das interfaces de debug](https://www.intel.com/content/www/us/en/developer/articles/technical/software-security-guidance/secure-coding/intel-debug-technology.html)

Nenhuma alteração em BIOS, MSR, fuses, microcódigo, clocks ou contagem de núcleos foi aplicada.
