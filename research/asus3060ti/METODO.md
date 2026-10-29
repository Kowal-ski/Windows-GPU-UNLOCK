# Método e limites

## Origem e adaptação

O mecanismo de unlock vem de Zagitta/gpu-unlock e de seu port Windows por impacifist. A contribuição aqui é uma extensão estreita, diagnóstico, guardas de identidade/topologia, tratamento da captura, compatibilidade de testes host e documentação do experimento ASUS. Não é um mecanismo de unlock inventado do zero.

O caminho padrão continuou recusando esta placa. Uma opção experimental explícita acrescenta a identidade `248910de / 884f1043` e a tupla GA104 somente ao envelope em memória do gerador. `proven.json` não foi promovido. O build local exige chip `b74000a1`, 8192 MiB e PROM SHA-256 `2c6108c3c5fe6f6ff4d205f9ca2279c3b2f8fc35828fd5e8a5c31719d025df51`, além das guardas originais de recursos PCI e topologia.

Duas capturas reais foram analisadas com suas respectivas imagens. A liberação de console exige a topologia agregada correta; a presença de outro display GPU é recusada. O ajuste da comparação PCI aceita apenas os dois valores observados `001e0004 / 001f0004` em `0xa8`, sob identidade e layout fixados. Os demais bits permanecem exatos. A verificação de runtime do release não foi relaxada.

O parser passou a aceitar o formato atual de detalhes dos drivers e as continuações contíguas de device paths, com testes de regressão. Um teste de falha na topologia foi corrigido para danificar a aresta real de propriedade da GPU, em vez de uma aresta inicial não relacionada. Os testes host também aceitam o compilador LLVM-MinGW portátil.

## Sequência de validação

1. Diagnóstico UEFI somente leitura, PROM íntegra e duas coletas distintas. Não publicar os dumps: podem conter dados privados e material proprietário.
2. Geração do perfil experimental local e execução de 21 jobs host (RAM/fixtures, sem acesso ao hardware). Esse resultado precede o novo assistente; seus testes são uma suíte separada.
3. Build e conferência dos EFIs com assets originais verificados. Nenhuma ROM/VBIOS foi gravada permanentemente por este procedimento.
4. Um boot físico completou a transação: resultado 0, containment 0, quiesced 1, fault 0, retained 0, maps 0, FLR 1. O wrapper verificou o estado final e retornou ao Windows. Não equivale a testar vários ciclos frios; o horário de boot do Windows pode refletir inicialização rápida.
5. Comparação do mesmo microbenchmark cuBLAS, mesmas bibliotecas, driver, script e limites de potência. Três processos por condição, matrizes 4096², aquecimento e 30 amostras por modo, temporização CUDA e comparações completas. Havia testes CPU concorrentes no baseline, uma limitação do controle experimental. Resultados não extrapolam para aplicações.
6. Testes numéricos suplementares com matrizes aleatórias inteiras e referência CPU float64; controle negativo detectou saída adulterada. O teste de dois minutos validou novamente todos os quatro modos.

## Números observados

| Modo | Antes (TFLOPS) | Depois (TFLOPS) | Variação |
|---|---:|---:|---:|
| FP32 pedantic | 11,4364 | 11,3441 | -0,81% |
| FP16 / acumulação FP32 | 35,8265 | 67,4758 | +88,34% |
| BF16 / acumulação FP32 | 35,7119 | 67,4403 | +88,85% |
| TF32 / acumulação FP32 | 18,1527 | 34,5744 | +90,46% |

O script GEMM publicado mantém `unlock_performed: false` em seu contexto porque **o próprio benchmark não executa unlock**; essa chave não identifica o estado prévio do hardware. A condição antes/depois vem da sequência de boot documentada e dos diretórios de resultados. Não usar essa chave isolada como classificador.

Os números são observações de uma única máquina. Não demonstram novos SMs, memória adicional, barramento maior, ganho universal, nem Frame Generation oficial. A suíte host pode ser repetida a partir de capturas locais; não se fornecem fixtures privadas para copiar a identidade desta máquina. O novo assistente foi testado com arquivos temporários e com inventário real somente leitura; seu fluxo inteiro ainda não foi repetido em outra máquina.

## Integridade e distribuição

[evidence/validation.json](evidence/validation.json) contém apenas campos selecionados, hashes e limites. Nenhum UUID, GUID de ESP, serial, dump, DLL de driver ou asset NVIDIA é necessário no repositório público. Os EFIs são personalizados: o usuário deve gerar os seus a partir de evidência própria. Mantenha as licenças e atribuições do projeto e dos inputs originais.
