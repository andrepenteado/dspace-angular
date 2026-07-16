import { filter, map } from 'rxjs/operators';
import { ChangeDetectionStrategy, Component, Inject, OnDestroy, OnInit, PLATFORM_ID } from '@angular/core';
import { ActivatedRoute, Data, Router } from '@angular/router';

import { BehaviorSubject, Observable } from 'rxjs';

import { ItemPageComponent } from '../simple/item-page.component';
import { MetadataMap, MetadataValue } from '../../core/shared/metadata.models';
import { ItemDataService } from '../../core/data/item-data.service';

import { RemoteData } from '../../core/data/remote-data';
import { Item } from '../../core/shared/item.model';

import { fadeInOut } from '../../shared/animations/fade';
import { hasValue } from '../../shared/empty.util';
import { KeyValue, Location } from '@angular/common';
import { AuthorizationDataService } from '../../core/data/feature-authorization/authorization-data.service';
import { ServerResponseService } from '../../core/services/server-response.service';
import { SignpostingDataService } from '../../core/data/signposting-data.service';
import { LinkHeadService } from '../../core/services/link-head.service';
import { APP_CONFIG, AppConfig } from '../../../config/app-config.interface';

/**
 * This component renders a full item page.
 * The route parameter 'id' is used to request the item it represents.
 */

@Component({
  selector: 'ds-full-item-page',
  styleUrls: ['./full-item-page.component.scss'],
  templateUrl: './full-item-page.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
  animations: [fadeInOut]
})
export class FullItemPageComponent extends ItemPageComponent implements OnInit, OnDestroy {

  itemRD$: BehaviorSubject<RemoteData<Item>>;

  metadata$: Observable<MetadataMap>;

  /**
   * Ordem de exibição dos metadados na tabela: segue a ordem das chaves de
   * `acessoAcademico.itemPage.labelsMetadados` no config do deployment.
   */
  private ordemMetadados: string[] = [];

  /**
   * True when the itemRD has been originated from its workspaceite/workflowitem, false otherwise.
   */
  fromSubmissionObject = false;

  subs = [];

  constructor(
    protected route: ActivatedRoute,
    protected router: Router,
    protected items: ItemDataService,
    protected authorizationService: AuthorizationDataService,
    protected _location: Location,
    protected responseService: ServerResponseService,
    protected signpostingDataService: SignpostingDataService,
    protected linkHeadService: LinkHeadService,
    @Inject(PLATFORM_ID) protected platformId: string,
    @Inject(APP_CONFIG) public appConfig: AppConfig,
  ) {
    super(route, router, items, authorizationService, responseService, signpostingDataService, linkHeadService, platformId);
  }

  /*** AoT inheritance fix, will hopefully be resolved in the near future **/
  ngOnInit(): void {
    super.ngOnInit();
    this.ordemMetadados = Object.keys(this.appConfig.acessoAcademico?.itemPage?.labelsMetadados ?? {});
    this.metadata$ = this.itemRD$.pipe(
      map((rd: RemoteData<Item>) => rd.payload),
      filter((item: Item) => hasValue(item)),
      map((item: Item) => item.metadata),);

    this.subs.push(this.route.data.subscribe((data: Data) => {
        this.fromSubmissionObject = hasValue(data.wfi) || hasValue(data.wsi);
      })
    );
  }

  /**
   * Comparador do pipe `keyvalue`: ordena os metadados conforme a posição da
   * chave em `labelsMetadados`; chaves sem label ficam no fim, em ordem
   * alfabética.
   */
  compararMetadados = (a: KeyValue<string, MetadataValue[]>, b: KeyValue<string, MetadataValue[]>): number => {
    const posA = this.ordemMetadados.indexOf(a.key);
    const posB = this.ordemMetadados.indexOf(b.key);
    if (posA === -1 && posB === -1) {
      return a.key.localeCompare(b.key);
    }
    if (posA === -1) {
      return 1;
    }
    if (posB === -1) {
      return -1;
    }
    return posA - posB;
  };

  /**
   * Navigate back in browser history.
   */
  back() {
    this._location.back();
  }

  ngOnDestroy() {
    this.subs.filter((sub) => hasValue(sub)).forEach((sub) => sub.unsubscribe());
  }
}
