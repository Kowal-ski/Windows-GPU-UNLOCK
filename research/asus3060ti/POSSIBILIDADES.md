# Possibilidades: IA local e limites físicos

Registro vivo de pesquisa, 2026-10-29. Escopo confirmado pelo usuário: **IA local, sem frente de jogos**. Aceitamos protótipos novos sem garantia de retorno; cada hipótese precisa de teste pequeno com critério de parada. Esta lista reúne possibilidades identificadas, não uma promessa de esgotar toda a pesquisa existente.

## Duas frentes em andamento

1. Publicar a extensão ASUS e um assistente reproduzível: código, documentação, guardas, testes e evidência selecionada. Sem assets proprietários ou dados privados.
2. Reduzir gargalos de IA local, distinguindo PCIe, VRAM, RAM e cálculo. Otimizar a aplicação antes de investir em hipóteses de alteração física sem evidência.

## Medida inicial

`evidence/bandwidth.json`, protocolo `synchronous-copy-wallclock-v1`, 12 amostras após três aquecimentos por caminho/tamanho, buffers aleatórios de 16/64/256 MiB, comparação SHA-256 do buffer inteiro após cada conjunto. Sem mudar clocks, drivers, BIOS ou fechar aplicativos.

| Caminho, 256 MiB | GB/s decimais observados |
|---|---:|
| RAM→GPU, memória comum | 5,75 |
| RAM→GPU, pinned | 11,51 |
| GPU→RAM, memória comum | 4,51 |
| GPU→RAM, pinned | 9,99 |
| VRAM→VRAM, leitura + escrita | 403,10 |

Pinned aproximadamente dobrou RAM→GPU neste microteste. Não é duplicação do barramento físico nem demonstra ganho de tokens/s. D2D conta duas vezes o tamanho copiado; não comparar seu número diretamente com H2D/D2H. Atividade do desktop não controlada, uma execução, sem comparação antes/depois do unlock. Resultado interno de cópia não equivale a um kernel de inferência.

## Catálogo priorizado

| Caminho | Hipótese e experimento mínimo | Estado / limites |
|---|---|---|
| Modelo inteiro na VRAM | Quantização adequada + contexto/batch que caibam nos 8 GiB; medir tokens/s, TTFT e VRAM pico | Prioridade alta; escolher modelo com o usuário; não há modelo obrigatório definido |
| Quantização de pesos | Comparar Q4/Q5/Q8 ou formatos suportados pelo backend, mesma tarefa/contexto | Reduz bytes e capacidade exigida, mas altera precisão; kernels/formato importam; validar qualidade |
| KV cache quantizado | Comparar cache FP16/Q8/Q4 quando backend/modelo suportarem | Pode liberar VRAM para contexto/offload; qualidade e suporte variam |
| Flash Attention / kernels fundidos | Evitar materializar matrizes intermediárias e leituras repetidas | Verificar suporte real da versão/backend e medir; não apenas ligar flag |
| Manter pesos/cache residentes | Evitar descarregar/recarregar pesos e transferências por token; configurar retenção e concorrência | Prioridade alta; medir tráfego e tempo de recarga sem encerrar apps do usuário |
| Pinned buffers | Aplicar em transferências repetidas com pools reutilizados | Microteste positivo; custo de fixação e consumo de RAM precisam entrar no tempo total |
| Transferência assíncrona + pipeline | Sobrepor cópia do próximo bloco ao cálculo atual em streams com eventos | Protótipo; concorrência depende do runtime e recursos; confirmar por timeline |
| Batching e prefill separado do decode | Agrupar operações/cópias e ajustar microbatch | Pode aumentar throughput e piorar latência/VRAM; medir ambos |
| Offload seletivo | Escolher camadas/tensores em GPU conforme custo de bytes e cálculo | Evitar thrashing; não assumir que mais offload sempre ganha |
| Compressão sem perdas no PCIe | Comprimir no lado de origem, transferir menos bytes, descomprimir no destino via kernel compatível/nvCOMP | **Pesquisa sem garantia.** Usar dados reais; pesos já quantizados podem ter pouca redundância; não instalar camada genérica de driver |
| Representação compacta na VRAM | Ler blocos quantizados e desquantizar nos registradores/on-chip durante GEMM | Caminho existente em backends; testar kernels adequados. Descomprimir tudo na VRAM antes de usar pode eliminar o benefício |
| Codec/kernel próprio fundido | Integrar descompressão ao consumidor e evitar buffer intermediário grande | **Pode exigir desenvolvimento do zero, sem retorno garantido.** Primeiro provar vantagem em um tensor representativo |
| Layout, coalescência e alinhamento | Reduzir transações desperdiçadas, cópias de layout e stride ruim | Requer perfil do kernel; trocar layouts pode acrescentar conversões |
| CUDA Graphs e pools | Diminuir overhead por token, launches e alocações repetidas | Não aumenta barramento; pode ajudar workloads pequenos/CPU limitado |
| Speculative decoding | Modelo rascunho propõe tokens e o maior verifica em lote | Testar aceitação, VRAM e tokens/s; draft também custa; método/backend precisam preservar distribuição ou explicitar alteração |
| Prefix/KV reuse | Reaproveitar prefixos iguais em conversas e requisições | Medir cache hit e TTFT; respeitar contexto/isolamento; não acelera prefixo inédito |
| Contexto menor / sliding window suportada | Reduzir KV e custo de atenção | Muda capacidade da aplicação; não truncar contexto silenciosamente |
| Menos requisições paralelas | Evitar duplicação de KV e evicção de modelo | Ajuste depende da carga; comparar latência p50/p95 e throughput |
| CPU backend / número de threads | Medir 4 versus 8 threads em partes CPU e evitar oversubscription | i3 tem 4 núcleos/8 threads; hyperthreading não duplica largura de RAM |
| RAM dual-channel, timings e estabilidade | Conferir canais e medir throughput/latência; investigar timings viáveis a 2666 | 4×8 GiB configurados em 2666; mistos. Não basta módulo ter rótulo 3200; nenhum timing alterado |
| RAM/SSD e carregamento do modelo | Comparar carga fria/quente, mmap/prefetch quando suportados, evitar paginação | Pode melhorar TTFT/carregamento, sem alterar decode com tudo residente |
| ReBAR, PCIe link e economia de energia | Conferir estado e regressões antes de mexer | Link observado Gen3 x16. ReBAR não vira Gen4 nem garante ganho CUDA; só testar com método de retorno |
| Temperatura/potência/curva de eficiência | Medir throttling e clocks sustentados sob inferência real | Nenhuma alteração aplicada; aumentar watts não resolve tráfego; VRAM já tem clock observado acima do nominal reportado |
| Clock da VRAM | Incremento pequeno só depois de baseline e validação numérica prolongada | **Sem garantia.** Erros/correções podem reduzir desempenho; exige reversão e controle térmico |
| CPU turbo/limites sustentados | Medir frequência, temperatura e limitação de potência antes de ajustes | i3-10100 não é K/X; não prometer overclock por multiplicador |
| Núcleos Intel desativados | Investigar documentação exata do die/fuses sem escrever firmware | **Pesquisa de baixa prioridade, sem mecanismo demonstrado.** CPUID/semelhança com i5 não provam núcleo íntegro ou reativável; todos os 4 expostos estão ativos |
| Ampliar barramento físico / VRAM | Exigiria evidência de canais, encapsulamento, placa e firmware compatíveis | **Nenhum método demonstrado por software.** Não confundir compressão com aumento de fios/capacidade física; mod de hardware não é etapa autorizada deste trabalho |
| Plataforma/hardware diferente | Comparação custo/benefício se o teto físico dominar | Registrar como referência, sem compra recomendada antes de medir workload |

## Critério para compressão

Para B bytes, barramento efetivo L e razão r = original/comprimido:

`T_bruto = B/L`

`T_comprimido = T_compressao + B/(r*L) + T_descompressao + T_metadados/sincronizacao`

Exigir `T_comprimido < T_bruto` no fluxo completo, com comparação de integridade e memória extra contabilizada. Para dados estáticos, medir separadamente o custo inicial amortizável e o custo por token; não amortizar custo que se repete a cada camada/token. Para dados incompressíveis pode haver expansão. Comprimir e descomprimir só na CPU antes da cópia não reduz o tráfego PCIe. Descomprimir na GPU e gravar um tensor grande reduz PCIe, mas pode acrescentar tráfego na VRAM.

Primeiro testar amostras reais de pesos/KV/intermediários autorizados, formatos/compressibilidade e tempos. Buffer zerado é controle, nunca evidência de ganho em modelo real. Se o protótipo não vencer a transferência bruta incluindo overhead, registrar negativo e seguir para outra frente.

## Próximos testes

1. Escolher com o usuário o modelo de uso real. O inventário local encontrou Ollama e modelos já instalados; nenhum download é necessário para começar. Não publicar o inventário completo de modelos pessoais.
2. Baseline end-to-end fixando prompt, contexto, seed, versão, quantização, batch e concorrência; separar carga fria, prefill, decode, VRAM/RAM pico e qualidade.
3. Comparar residência/quantização/KV/Flash Attention disponíveis, uma variável por vez.
4. Prototipar pinned/overlap e compressão apenas se houver tráfego repetido relevante no perfil.
5. Guardar também resultados negativos e custo de engenharia; priorizar outra frente quando não surgir evidência.

## Fontes primárias consultadas

- [CUDA Best Practices: minimizar transferências, pinned, overlap e coalescência](https://docs.nvidia.com/cuda/cuda-c-best-practices-guide/index.html).
- [nvCOMP: compressão sem perdas na GPU](https://docs.nvidia.com/cuda/nvcomp/) e [visão geral](https://developer.nvidia.com/nvcomp). Confirmar suporte de versão/formato à Ampere antes de integrar; o decompressor dedicado de Blackwell não existe nesta RTX.
- [llama.cpp: implementação de KV cache e quantização](https://github.com/ggml-org/llama.cpp/blob/master/src/llama-kv-cache.cpp). Flags e compatibilidade precisam ser conferidas na versão instalada.
- [Intel i3-10100: 4 cores, 8 threads, DDR4-2666](https://www.intel.com/content/www/us/en/products/sku/199283/intel-core-i310100-processor-6m-cache-up-to-4-30-ghz/specifications.html).
- [Intel: processadores K/X desbloqueados para overclock](https://www.intel.com/content/www/us/en/support/articles/000038213.html).

## i3 e RAM: triagem adicional

O inventário confirmou i3-10100, 4 núcleos habilitados e 8 processadores lógicos; 4 módulos de 8 GiB, todos configurados em 2666 MT/s. O campo WMI de clock não é uma medição de turbo sustentado sob carga.

`cpu_ram.py` executou cópia de 256 MiB e GEMM FP32 1536² em processos separados, solicitando 4 e 8 threads ao BLAS. Resultados: **18,08 GB/s** na cópia RAM (leitura + escrita), **228,01 GFLOPS** com 4 threads solicitadas e **272,76 GFLOPS** com 8, aproximadamente **+19,6%** neste cálculo. As matrizes completas e buffers foram conferidos.

[evidence/cpu-ram.json](evidence/cpu-ram.json) guarda as amostras. É uma triagem curta, uma execução com desktop não controlado, sem telemetria térmica/frequência e sem confirmação independente da contagem de threads do backend. Não mede tokens/s, pico físico da RAM ou estabilidade de overclock. Não concluir daqui que 8 threads sempre vencem em inferência: decode CPU pode ser limitado pela RAM. O próximo teste útil compara 4/8 threads no mesmo modelo, com CPU/offload definidos e repetição.
